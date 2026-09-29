# ============================================================
# 🚚 DELIVERY ASSIGNMENT + BATCH ENGINE
# ============================================================

from datetime import datetime, date
from math import radians, sin, cos, sqrt, atan2
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.delivery_partner import DeliveryPartnerProfile
from app.models.delivery_order import DeliveryOrder
from app.models.delivery_batch import DeliveryBatch
from app.models.order import Order
from app.models.order_item import OrderItem


# ============================================================
# CONFIG
# ============================================================

MAX_TIFFINS_PER_BATCH = 30

ELIGIBLE_DELIVERY_STATUSES = {
    "waiting",
}

ACTIVE_BATCH_STATUSES = {
    "created",
    "assigned",
    "started",
}


# ============================================================
# HAVERSINE DISTANCE
# Returns distance in KM
# ============================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    if (
        lat1 is None
        or lon1 is None
        or lat2 is None
        or lon2 is None
    ):
        return None

    lat1 = radians(float(lat1))
    lon1 = radians(float(lon1))

    lat2 = radians(float(lat2))
    lon2 = radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        +
        cos(lat1)
        * cos(lat2)
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a),
    )

    return 6371.0 * c


# ============================================================
# GET DELIVERY DATE
#
# OrderItem.menu_date already contains:
# - normal menu date
# - Tomorrow Special date
# ============================================================

def get_delivery_date(
    db: Session,
    order_id,
):
    item_date = (
        db.query(OrderItem.menu_date)
        .filter(
            OrderItem.order_id == order_id,
            OrderItem.menu_date.isnot(None),
        )
        .order_by(OrderItem.menu_date.asc())
        .first()
    )

    if item_date and item_date[0]:
        return item_date[0]

    # Fallback: today
    return date.today()


# ============================================================
# GET ELIGIBLE DELIVERY PARTNERS
# ============================================================

def get_eligible_delivery_partners(
    db: Session,
):
    rows = (
        db.query(
            User,
            DeliveryPartnerProfile,
        )
        .join(
            DeliveryPartnerProfile,
            DeliveryPartnerProfile.user_id == User.id,
        )
        .filter(
            User.role == "delivery_partner",
            User.is_active == True,
            User.application_status == "approved",

            DeliveryPartnerProfile.application_status
            == "approved",

            DeliveryPartnerProfile.is_online == True,
            DeliveryPartnerProfile.is_available == True,

            DeliveryPartnerProfile.current_latitude
            .isnot(None),

            DeliveryPartnerProfile.current_longitude
            .isnot(None),
        )
        .all()
    )

    return rows


# ============================================================
# CHECK ACTIVE BATCH FOR DRIVER
# ============================================================

def get_active_batch_for_driver(
    db: Session,
    driver_id,
    delivery_date,
    meal_type,
):
    return (
        db.query(DeliveryBatch)
        .filter(
            DeliveryBatch.delivery_partner_id
            == driver_id,

            DeliveryBatch.delivery_date
            == delivery_date,

            DeliveryBatch.meal_type
            == meal_type,

            DeliveryBatch.status.in_(
                list(ACTIVE_BATCH_STATUSES)
            ),
        )
        .order_by(
            DeliveryBatch.created_at.desc()
        )
        .first()
    )


# ============================================================
# CALCULATE EXISTING BATCH TIFFINS
# ============================================================

def get_batch_tiffins(
    db: Session,
    batch_id,
):
    total = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.batch_id == batch_id
        )
        .with_entities(
            DeliveryOrder.total_tiffins
        )
        .all()
    )

    return sum(
        int(row[0] or 0)
        for row in total
    )


# ============================================================
# GET NEXT SEQUENCE
# ============================================================

def get_next_sequence(
    db: Session,
    batch_id,
):
    last_order = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.batch_id == batch_id
        )
        .order_by(
            DeliveryOrder.sequence_no.desc()
        )
        .first()
    )

    if not last_order:
        return 1

    return int(
        last_order.sequence_no or 0
    ) + 1


# ============================================================
# GET UNASSIGNED READY DELIVERY ORDERS
# ============================================================

def get_waiting_ready_orders(
    db: Session,
    delivery_date=None,
    meal_type=None,
):
    query = (
        db.query(
            DeliveryOrder,
            Order,
        )
        .join(
            Order,
            Order.id == DeliveryOrder.order_id,
        )
        .filter(
            DeliveryOrder.delivery_status == "waiting",

            DeliveryOrder.delivery_partner_id.is_(None),

            DeliveryOrder.batch_id.is_(None),

            # VERY IMPORTANT
            # Delivery partner gets order only
            # after chef marks it READY.
            Order.status == "ready",

            DeliveryOrder.latitude.isnot(None),

            DeliveryOrder.longitude.isnot(None),
        )
    )

    if delivery_date:
        query = query.filter(
            DeliveryOrder.order_id.in_(
                db.query(OrderItem.order_id)
                .filter(
                    OrderItem.menu_date
                    == delivery_date
                )
            )
        )

    if meal_type:
        query = query.filter(
            DeliveryOrder.meal_type
            == meal_type
        )

    return (
        query
        .order_by(
            DeliveryOrder.created_at.asc()
        )
        .all()
    )


# ============================================================
# PICK BEST DRIVER
#
# We choose driver nearest to the first delivery point.
# Later this can be replaced with Google Routes / Maps API.
# ============================================================

def choose_best_driver(
    drivers,
    delivery_order,
):
    best_driver = None
    best_distance = None

    for user, profile in drivers:

        distance = haversine_km(
            profile.current_latitude,
            profile.current_longitude,
            delivery_order.latitude,
            delivery_order.longitude,
        )

        if distance is None:
            continue

        if (
            best_distance is None
            or distance < best_distance
        ):
            best_distance = distance
            best_driver = (
                user,
                profile,
                distance,
            )

    return best_driver


# ============================================================
# SORT ORDERS FOR A DRIVER
#
# Greedy nearest-neighbour routing:
#
# driver location
#      ↓
# nearest customer
#      ↓
# next nearest customer
#      ↓
# next nearest customer
#
# This reduces unnecessary travel compared with random order.
# ============================================================

def optimize_order_sequence(
    driver_lat,
    driver_lon,
    orders,
):
    remaining = list(orders)

    optimized = []

    current_lat = driver_lat
    current_lon = driver_lon

    while remaining:

        best = None
        best_distance = None

        for delivery_order, order in remaining:

            distance = haversine_km(
                current_lat,
                current_lon,
                delivery_order.latitude,
                delivery_order.longitude,
            )

            if distance is None:
                continue

            if (
                best_distance is None
                or distance < best_distance
            ):
                best_distance = distance
                best = (
                    delivery_order,
                    order,
                )

        if best is None:
            break

        optimized.append(best)
        remaining.remove(best)

        current_lat = best[0].latitude
        current_lon = best[0].longitude

    return optimized


# ============================================================
# CREATE NEW BATCH
# ============================================================

def create_batch(
    db: Session,
    driver_id,
    delivery_date,
    meal_type,
):
    batch = DeliveryBatch(
        delivery_partner_id=driver_id,

        delivery_date=delivery_date,

        meal_type=meal_type,

        status="created",

        total_orders=0,

        total_tiffins=0,

        start_latitude=None,

        start_longitude=None,

        created_at=datetime.utcnow(),

        assigned_at=None,

        started_at=None,

        completed_at=None,
    )

    db.add(batch)
    db.flush()

    return batch


# ============================================================
# ASSIGN ONE DELIVERY ORDER
# ============================================================

def assign_delivery_order(
    db: Session,
    delivery_order,
    batch,
    sequence_no,
):
    delivery_order.delivery_partner_id = (
        batch.delivery_partner_id
    )

    delivery_order.batch_id = batch.id

    delivery_order.sequence_no = sequence_no

    delivery_order.delivery_status = "assigned"

    delivery_order.assigned_at = (
        datetime.utcnow()
    )

    db.add(delivery_order)


# ============================================================
# MAIN ASSIGNMENT ENGINE
# ============================================================

# ============================================================
# MAIN ASSIGNMENT ENGINE
# ============================================================

def run_delivery_assignment(
    db: Session,
    delivery_date=None,
    meal_type=None,
):
    """
    Main automatic delivery assignment engine.

    Rules:
    - Only READY orders
    - Only waiting delivery orders
    - Only approved/active drivers
    - Driver must be online + available
    - Driver location required
    - Max 30 TIFFINS per batch
    - Meal types stay separated
    - Driver receives dynamic assignment
    """

    # --------------------------------------------------------
    # 1. GET ELIGIBLE DRIVERS
    # --------------------------------------------------------

    drivers = get_eligible_delivery_partners(db)

    if not drivers:
        return {
            "success": True,
            "message": (
                "No eligible delivery partners available"
            ),
            "assigned_orders": 0,
            "assigned_tiffins": 0,
            "batches_created": 0,
            "unassigned_orders": 0,
            "assignments": [],
        }

    # --------------------------------------------------------
    # 2. GET WAITING + READY ORDERS
    # --------------------------------------------------------

    waiting_orders = get_waiting_ready_orders(
        db=db,
        delivery_date=delivery_date,
        meal_type=meal_type,
    )

    if not waiting_orders:
        return {
            "success": True,
            "message": (
                "No READY delivery orders waiting for assignment"
            ),
            "assigned_orders": 0,
            "assigned_tiffins": 0,
            "batches_created": 0,
            "unassigned_orders": 0,
            "assignments": [],
        }

    # --------------------------------------------------------
    # 3. GROUP ORDERS BY:
    #
    # delivery_date + meal_type
    #
    # Example:
    #
    # 29 Sep + special
    # 29 Sep + lunch
    # 30 Sep + breakfast
    # --------------------------------------------------------

    groups = defaultdict(list)

    for delivery_order, order in waiting_orders:

        target_date = get_delivery_date(
            db,
            order.id,
        )

        target_meal = (
            delivery_order.meal_type
            or "mixed"
        )

        groups[
            (
                target_date,
                target_meal,
            )
        ].append(
            (
                delivery_order,
                order,
            )
        )

    # --------------------------------------------------------
    # RESULT COUNTERS
    # --------------------------------------------------------

    assigned_orders_count = 0
    assigned_tiffins_count = 0
    batches_created_count = 0

    assignment_results = []

    # --------------------------------------------------------
    # 4. PROCESS EACH DATE + MEAL GROUP
    # --------------------------------------------------------

    for (
        group_date,
        group_meal,
    ), group_orders in groups.items():

        # Copy group orders
        remaining = list(group_orders)

        # ----------------------------------------------------
        # KEEP PROCESSING UNTIL:
        #
        # - all orders assigned
        # OR
        # - no driver available
        # ----------------------------------------------------

        while remaining:

            # ------------------------------------------------
            # FIND BEST DRIVER + BEST ORDER
            #
            # Driver nearest to customer
            # ------------------------------------------------

            best_driver = None
            best_order = None
            best_distance = None

            for delivery_order, order in remaining:

                selected = choose_best_driver(
                    drivers,
                    delivery_order,
                )

                if selected is None:
                    continue

                user, profile, distance = selected

                if (
                    best_distance is None
                    or distance < best_distance
                ):
                    best_distance = distance

                    best_driver = (
                        user,
                        profile,
                    )

                    best_order = (
                        delivery_order,
                        order,
                    )

            # ------------------------------------------------
            # NO DRIVER AVAILABLE
            # ------------------------------------------------

            if best_driver is None:
                break

            driver_user, driver_profile = (
                best_driver
            )

            # ------------------------------------------------
            # CHECK EXISTING ACTIVE BATCH
            # ------------------------------------------------

            batch = get_active_batch_for_driver(
                db=db,
                driver_id=driver_user.id,
                delivery_date=group_date,
                meal_type=group_meal,
            )

            # ------------------------------------------------
            # CREATE NEW BATCH
            # ------------------------------------------------

            if batch is None:

                batch = create_batch(
                    db=db,
                    driver_id=driver_user.id,
                    delivery_date=group_date,
                    meal_type=group_meal,
                )

                batches_created_count += 1

                # Driver is now busy
                driver_profile.is_available = False

                # Save driver's location as batch start
                batch.start_latitude = (
                    driver_profile.current_latitude
                )

                batch.start_longitude = (
                    driver_profile.current_longitude
                )

                batch.assigned_at = (
                    datetime.utcnow()
                )

                db.add(batch)
                db.add(driver_profile)

                # Make sure batch exists in DB
                db.flush()

            # ------------------------------------------------
            # CURRENT BATCH TIFFINS
            # ------------------------------------------------

            current_tiffins = get_batch_tiffins(
                db=db,
                batch_id=batch.id,
            )

            remaining_capacity = (
                MAX_TIFFINS_PER_BATCH
                - current_tiffins
            )

            # ------------------------------------------------
            # BATCH FULL
            # ------------------------------------------------

            if remaining_capacity <= 0:

                # Driver cannot take more
                driver_profile.is_available = False

                db.add(driver_profile)

                # Remove this driver from this assignment run
                drivers = [
                    item
                    for item in drivers
                    if item[0].id != driver_user.id
                ]

                if not drivers:
                    break

                continue

            # ------------------------------------------------
            # FIND ORDERS THAT FIT INSIDE 30 TIFFIN LIMIT
            # ------------------------------------------------

            fitting_orders = [
                item
                for item in remaining
                if int(
                    item[0].total_tiffins or 0
                ) <= remaining_capacity
            ]

            # ------------------------------------------------
            # NO ORDER FITS
            # ------------------------------------------------

            if not fitting_orders:

                drivers = [
                    item
                    for item in drivers
                    if item[0].id != driver_user.id
                ]

                if not drivers:
                    break

                continue

            # ------------------------------------------------
            # OPTIMIZE DELIVERY ORDER
            #
            # Driver location
            #       ↓
            # nearest customer
            #       ↓
            # next nearest customer
            #       ↓
            # next nearest customer
            # ------------------------------------------------

            optimized = optimize_order_sequence(
                driver_profile.current_latitude,
                driver_profile.current_longitude,
                fitting_orders,
            )

            if not optimized:
                break

            # ------------------------------------------------
            # ASSIGN ORDERS
            # ------------------------------------------------

            batch_current_tiffins = current_tiffins

            sequence_no = get_next_sequence(
                db=db,
                batch_id=batch.id,
            )

            assigned_from_group = []

            for delivery_order, order in optimized:

                quantity = int(
                    delivery_order.total_tiffins
                    or 0
                )

                # --------------------------------------------
                # Check 30 TIFFIN limit
                # --------------------------------------------

                if (
                    batch_current_tiffins
                    + quantity
                    > MAX_TIFFINS_PER_BATCH
                ):
                    continue

                # --------------------------------------------
                # Assign delivery order
                # --------------------------------------------

                assign_delivery_order(
                    db=db,
                    delivery_order=delivery_order,
                    batch=batch,
                    sequence_no=sequence_no,
                )

                # --------------------------------------------
                # Update counters
                # --------------------------------------------

                batch_current_tiffins += quantity

                sequence_no += 1

                assigned_orders_count += 1

                assigned_tiffins_count += quantity

                assigned_from_group.append(
                    delivery_order
                )

                # --------------------------------------------
                # Assignment response
                # --------------------------------------------

                assignment_results.append(
                    {
                        "delivery_order_id": str(
                            delivery_order.id
                        ),

                        "order_id": str(
                            delivery_order.order_id
                        ),

                        "delivery_partner_id": str(
                            driver_user.id
                        ),

                        "batch_id": str(
                            batch.id
                        ),

                        "sequence_no": (
                            delivery_order.sequence_no
                        ),

                        "tiffins": quantity,

                        "meal_type": group_meal,

                        "delivery_date": str(
                            group_date
                        ),

                        "distance_from_driver_km": (
                            round(
                                haversine_km(
                                    driver_profile.current_latitude,
                                    driver_profile.current_longitude,
                                    delivery_order.latitude,
                                    delivery_order.longitude,
                                ),
                                3,
                            )
                        ),
                    }
                )

            # ------------------------------------------------
            # IMPORTANT
            #
            # DeliveryOrder records were added using db.add()
            # but may not yet be visible to count queries.
            #
            # Flush first.
            # ------------------------------------------------

            db.flush()

            # ------------------------------------------------
            # RECALCULATE BATCH TOTALS FROM DATABASE
            # ------------------------------------------------

            batch_orders = (
                db.query(DeliveryOrder)
                .filter(
                    DeliveryOrder.batch_id
                    == batch.id
                )
                .all()
            )

            # Total number of orders
            batch.total_orders = len(
                batch_orders
            )

            # Total number of tiffins
            batch.total_tiffins = sum(
                int(
                    delivery_order.total_tiffins
                    or 0
                )
                for delivery_order
                in batch_orders
            )

            # ------------------------------------------------
            # BATCH STATUS
            # ------------------------------------------------

            batch.status = "assigned"

            if not batch.assigned_at:
                batch.assigned_at = (
                    datetime.utcnow()
                )

            db.add(batch)

            # ------------------------------------------------
            # REMOVE ASSIGNED ORDERS
            # ------------------------------------------------

            assigned_ids = {
                item.id
                for item in assigned_from_group
            }

            remaining = [
                item
                for item in remaining
                if item[0].id
                not in assigned_ids
            ]

            # ------------------------------------------------
            # DRIVER BECOMES BUSY
            # ------------------------------------------------

            driver_profile.is_available = False

            db.add(driver_profile)

            # ------------------------------------------------
            # IF NO MORE ORDERS
            # ------------------------------------------------

            if not remaining:
                break

            # ------------------------------------------------
            # DRIVER ALREADY HAS A BATCH
            #
            # Don't assign another batch to same driver
            # during this assignment run.
            # ------------------------------------------------

            drivers = [
                item
                for item in drivers
                if item[0].id != driver_user.id
            ]

            if not drivers:
                break

    # --------------------------------------------------------
    # 5. COMMIT ALL ASSIGNMENTS
    # --------------------------------------------------------

    db.commit()

    # --------------------------------------------------------
    # 6. FINAL UNASSIGNED COUNT
    # --------------------------------------------------------

    unassigned_query = (
        db.query(DeliveryOrder)
        .filter(
            DeliveryOrder.delivery_status
            == "waiting",

            DeliveryOrder.delivery_partner_id
            .is_(None),

            DeliveryOrder.batch_id
            .is_(None),
        )
    )

    # --------------------------------------------------------
    # FILTER DATE
    # --------------------------------------------------------

    if delivery_date:

        order_ids = (
            db.query(
                OrderItem.order_id
            )
            .filter(
                OrderItem.menu_date
                == delivery_date
            )
        )

        unassigned_query = (
            unassigned_query
            .filter(
                DeliveryOrder.order_id.in_(
                    order_ids
                )
            )
        )

    # --------------------------------------------------------
    # FILTER MEAL TYPE
    # --------------------------------------------------------

    if meal_type:

        unassigned_query = (
            unassigned_query
            .filter(
                DeliveryOrder.meal_type
                == meal_type
            )
        )

    unassigned_orders_count = (
        unassigned_query.count()
    )

    # --------------------------------------------------------
    # 7. FINAL RESPONSE
    # --------------------------------------------------------

    return {
        "success": True,

        "message": (
            "Delivery assignment completed"
        ),

        "max_tiffins_per_batch": (
            MAX_TIFFINS_PER_BATCH
        ),

        "assigned_orders": (
            assigned_orders_count
        ),

        "assigned_tiffins": (
            assigned_tiffins_count
        ),

        "batches_created": (
            batches_created_count
        ),

        "unassigned_orders": (
            unassigned_orders_count
        ),

        "assignments": (
            assignment_results
        ),
    }