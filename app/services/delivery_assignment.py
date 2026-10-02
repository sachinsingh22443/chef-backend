# ============================================================
# 🚚 DELIVERY ASSIGNMENT + BATCH ENGINE
# ============================================================

from datetime import datetime, date
from math import radians, sin, cos, sqrt, atan2
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.delivery_partner import DeliveryPartnerProfile
from app.models.delivery_batch_pickup import DeliveryBatchPickup
from app.models.user import ChefProfile
from app.models.delivery_order import DeliveryOrder
from app.models.delivery_batch import DeliveryBatch
from app.models.order import Order
from app.models.order_item import OrderItem


# ============================================================
# CONFIG
# ============================================================

MAX_TIFFINS_PER_BATCH = 30
CLUSTER_RADIUS_KM = 2.0

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


# ============================================================
# GET CLUSTER CENTER
# ============================================================

def get_cluster_center(cluster):
    """
    Calculate geographical center of a cluster.

    cluster format:
    [
        (delivery_order, order),
        ...
    ]

    Returns:
        (latitude, longitude)
    """

    valid_points = []

    for delivery_order, order in cluster:

        if (
            delivery_order.latitude is None
            or delivery_order.longitude is None
        ):
            continue

        valid_points.append(
            (
                float(delivery_order.latitude),
                float(delivery_order.longitude),
            )
        )

    if not valid_points:
        return None, None

    latitude = sum(
        point[0]
        for point in valid_points
    ) / len(valid_points)

    longitude = sum(
        point[1]
        for point in valid_points
    ) / len(valid_points)

    return latitude, longitude


# ============================================================
# BUILD GEOGRAPHICAL CLUSTERS
# ============================================================

def build_geographical_clusters(
    orders,
    radius_km=CLUSTER_RADIUS_KM,
):
    """
    Group delivery orders geographically.

    Important rules:
    - Orders must already belong to same date + meal group.
    - A cluster is created around a seed order.
    - New orders are added only when they are within
      radius_km of the current cluster center.
    - No tiffin limit is applied here.
    - 30-tiffin splitting happens later.

    Returns:
        [
            [
                (delivery_order, order),
                ...
            ],
            ...
        ]
    """

    remaining = list(orders)
    clusters = []

    while remaining:

        # ----------------------------------------------------
        # Take oldest order as cluster seed
        # ----------------------------------------------------

        seed = remaining.pop(0)

        seed_order = seed[0]

        cluster = [seed]

        # ----------------------------------------------------
        # Initial cluster center
        # ----------------------------------------------------

        center_lat = seed_order.latitude
        center_lon = seed_order.longitude

        if (
            center_lat is None
            or center_lon is None
        ):
            clusters.append(cluster)
            continue

        # ----------------------------------------------------
        # Find nearby orders
        # ----------------------------------------------------

        nearby = []

        for item in remaining:

            delivery_order, order = item

            if (
                delivery_order.latitude is None
                or delivery_order.longitude is None
            ):
                continue

            distance = haversine_km(
                center_lat,
                center_lon,
                delivery_order.latitude,
                delivery_order.longitude,
            )

            if (
                distance is not None
                and distance <= radius_km
            ):
                nearby.append(item)

        # ----------------------------------------------------
        # Add nearby orders
        # ----------------------------------------------------

        for item in nearby:

            cluster.append(item)

            remaining.remove(item)

            # Recalculate cluster center
            center_lat, center_lon = (
                get_cluster_center(cluster)
            )

        clusters.append(cluster)

    return clusters


# ============================================================
# SPLIT CLUSTER INTO MAX 30 TIFFIN BATCH GROUPS
# ============================================================

def split_cluster_by_tiffin_capacity(
    cluster,
    max_tiffins=MAX_TIFFINS_PER_BATCH,
):
    """
    Split one geographical cluster into groups
    of maximum 30 tiffins.

    Important:
    - Individual order is never split.
    - One order greater than 30 tiffins cannot be assigned.
    """

    batches = []

    current_batch = []
    current_tiffins = 0

    # --------------------------------------------------------
    # Keep geographically close orders together.
    # --------------------------------------------------------

    cluster_center = get_cluster_center(cluster)

    if cluster_center == (None, None):
        return []

    center_lat, center_lon = cluster_center

    sorted_cluster = sorted(
        cluster,
        key=lambda item: (
            haversine_km(
                center_lat,
                center_lon,
                item[0].latitude,
                item[0].longitude,
            )
            or float("inf")
        ),
    )

    for item in sorted_cluster:

        delivery_order, order = item

        quantity = int(
            delivery_order.total_tiffins or 0
        )

        # ----------------------------------------------------
        # Invalid / zero quantity
        # ----------------------------------------------------

        if quantity <= 0:
            continue

        # ----------------------------------------------------
        # Single order larger than batch capacity
        # ----------------------------------------------------

        if quantity > max_tiffins:
            continue

        # ----------------------------------------------------
        # Does order fit?
        # ----------------------------------------------------

        if (
            current_tiffins + quantity
            <= max_tiffins
        ):

            current_batch.append(item)

            current_tiffins += quantity

        else:

            if current_batch:
                batches.append(current_batch)

            current_batch = [item]
            current_tiffins = quantity

    # --------------------------------------------------------
    # Add final batch
    # --------------------------------------------------------

    if current_batch:
        batches.append(current_batch)

    return batches


# ============================================================
# CHOOSE DRIVER FOR GEOGRAPHICAL CLUSTER
# ============================================================

def choose_best_driver_for_cluster(
    drivers,
    cluster,
):
    """
    Select driver closest to geographical center
    of the cluster.
    """

    center_lat, center_lon = (
        get_cluster_center(cluster)
    )

    if (
        center_lat is None
        or center_lon is None
    ):
        return None

    best_driver = None
    best_distance = None

    for user, profile in drivers:

        distance = haversine_km(
            profile.current_latitude,
            profile.current_longitude,
            center_lat,
            center_lon,
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
# CREATE CHEF-WISE PICKUP STOPS FOR BATCH
# ============================================================

# ============================================================
# CREATE / UPDATE CHEF-WISE PICKUP STOPS FOR BATCH
# ============================================================

def create_batch_pickup_stops(
    db: Session,
    batch: DeliveryBatch,
    delivery_orders,
    driver_latitude=None,
    driver_longitude=None,
):
    """
    Create / update chef-wise pickup stops.

    Rules:
    - One chef = one pickup stop per batch
    - Multiple orders of same chef are combined
    - Chef name comes from User
    - ChefProfile is optional
    - Chef location is taken from ChefProfile when available
    - Existing pickup is updated instead of duplicated
    - Existing pickup status is preserved
    """

    # --------------------------------------------------------
    # 1. GROUP TIFFINS BY CHEF
    # --------------------------------------------------------

    chef_groups = defaultdict(int)

    for delivery_order, order in delivery_orders:

        chef_id = getattr(order, "chef_id", None)

        if not chef_id:
            continue

        quantity = int(
            delivery_order.total_tiffins or 0
        )

        if quantity <= 0:
            continue

        chef_groups[chef_id] += quantity

    if not chef_groups:
        return []

    # --------------------------------------------------------
    # 2. GET CHEFS
    #
    # IMPORTANT:
    # Do NOT use INNER JOIN with ChefProfile.
    # ChefProfile may be missing.
    # --------------------------------------------------------

    chef_ids = list(chef_groups.keys())

    chef_users = (
        db.query(User)
        .filter(
            User.id.in_(chef_ids)
        )
        .all()
    )

    chef_profiles = (
        db.query(ChefProfile)
        .filter(
            ChefProfile.user_id.in_(chef_ids)
        )
        .all()
    )

    profile_map = {
        profile.user_id: profile
        for profile in chef_profiles
    }

    user_map = {
        user.id: user
        for user in chef_users
    }

    # --------------------------------------------------------
    # 3. PREPARE PICKUP POINTS
    # --------------------------------------------------------

    pickup_points = []

    for chef_id, expected_tiffins in chef_groups.items():

        if expected_tiffins <= 0:
            continue

        chef_user = user_map.get(chef_id)
        chef_profile = profile_map.get(chef_id)

        # ----------------------------------------------------
        # CHEF NAME
        # ----------------------------------------------------

        chef_name = (
            chef_user.name
            if chef_user and chef_user.name
            else "Chef"
        )

        # ----------------------------------------------------
        # CHEF LOCATION
        # ----------------------------------------------------

        latitude = None
        longitude = None
        kitchen_location = None

        if chef_profile:

            latitude = chef_profile.latitude
            longitude = chef_profile.longitude

            kitchen_location = (
                chef_profile.location
            )

        # ----------------------------------------------------
        # DISTANCE FROM DRIVER
        # ----------------------------------------------------

        distance = haversine_km(
            driver_latitude,
            driver_longitude,
            latitude,
            longitude,
        )

        pickup_points.append(
            {
                "chef_id": chef_id,
                "chef_name": chef_name,
                "kitchen_location": kitchen_location,
                "latitude": latitude,
                "longitude": longitude,
                "expected_tiffins": expected_tiffins,
                "distance": distance,
            }
        )

    # --------------------------------------------------------
    # 4. SPLIT VALID / INVALID LOCATIONS
    # --------------------------------------------------------

    valid_points = [
        point
        for point in pickup_points
        if (
            point["latitude"] is not None
            and point["longitude"] is not None
        )
    ]

    invalid_points = [
        point
        for point in pickup_points
        if (
            point["latitude"] is None
            or point["longitude"] is None
        )
    ]

    # --------------------------------------------------------
    # 5. OPTIMIZE PICKUP ROUTE
    # --------------------------------------------------------

    ordered_points = []

    remaining = list(valid_points)

    current_latitude = driver_latitude
    current_longitude = driver_longitude

    while remaining:

        best_point = None
        best_distance = None

        for point in remaining:

            distance = haversine_km(
                current_latitude,
                current_longitude,
                point["latitude"],
                point["longitude"],
            )

            if distance is None:
                continue

            if (
                best_distance is None
                or distance < best_distance
            ):
                best_distance = distance
                best_point = point

        if best_point is None:
            break

        ordered_points.append(best_point)
        remaining.remove(best_point)

        current_latitude = best_point["latitude"]
        current_longitude = best_point["longitude"]

    # --------------------------------------------------------
    # 6. CHEFS WITHOUT LOCATION AT END
    # --------------------------------------------------------

    ordered_points.extend(invalid_points)

    # --------------------------------------------------------
    # 7. CREATE / UPDATE PICKUPS
    # --------------------------------------------------------

    pickup_stops = []

    for sequence_no, point in enumerate(
        ordered_points,
        start=1,
    ):

        existing = (
            db.query(DeliveryBatchPickup)
            .filter(
                DeliveryBatchPickup.batch_id
                == batch.id,

                DeliveryBatchPickup.chef_id
                == point["chef_id"],
            )
            .first()
        )

        # ====================================================
        # UPDATE EXISTING PICKUP
        # ====================================================

        if existing:

            existing.sequence_no = sequence_no

            existing.chef_name = (
                point["chef_name"]
            )

            existing.kitchen_location = (
                point["kitchen_location"]
            )

            existing.latitude = (
                point["latitude"]
            )

            existing.longitude = (
                point["longitude"]
            )

            existing.expected_tiffins = (
                point["expected_tiffins"]
            )

            existing.updated_at = (
                datetime.utcnow()
            )

            db.add(existing)

            pickup_stops.append(existing)

            continue

        # ====================================================
        # CREATE NEW PICKUP
        # ====================================================

        pickup = DeliveryBatchPickup(
            batch_id=batch.id,

            chef_id=point["chef_id"],

            sequence_no=sequence_no,

            chef_name=point["chef_name"],

            kitchen_location=(
                point["kitchen_location"]
            ),

            latitude=point["latitude"],

            longitude=point["longitude"],

            expected_tiffins=(
                point["expected_tiffins"]
            ),

            received_tiffins=0,

            status="pending",

            arrived_at=None,

            picked_up_at=None,

            created_at=datetime.utcnow(),

            updated_at=datetime.utcnow(),
        )

        db.add(pickup)

        pickup_stops.append(pickup)

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    db.flush()

    return pickup_stops
# ============================================================
# ASSIGN ONE DELIVERY ORDER
# ============================================================
# ============================================================
# REPAIR EXISTING ACTIVE BATCH PICKUPS
# ============================================================

def repair_active_batch_pickups(
    db: Session,
):
    """
    Repair / rebuild pickup stops for all active batches.

    Useful when:
    - batch already exists
    - orders already assigned
    - pickup rows were not created
    - new orders were added to an existing batch
    """

    active_batches = (
        db.query(DeliveryBatch)
        .filter(
            DeliveryBatch.status.in_(
                list(ACTIVE_BATCH_STATUSES)
            )
        )
        .all()
    )

    repaired_batches = 0
    repaired_pickups = 0

    for batch in active_batches:

        batch_delivery_orders = (
            db.query(
                DeliveryOrder,
                Order,
            )
            .join(
                Order,
                Order.id
                == DeliveryOrder.order_id,
            )
            .filter(
                DeliveryOrder.batch_id
                == batch.id,
            )
            .all()
        )

        if not batch_delivery_orders:
            continue

        pickup_stops = (
            create_batch_pickup_stops(
                db=db,
                batch=batch,
                delivery_orders=batch_delivery_orders,
                driver_latitude=(
                    batch.start_latitude
                ),
                driver_longitude=(
                    batch.start_longitude
                ),
            )
        )

        # ----------------------------------------------------
        # RECALCULATE BATCH TOTALS
        # ----------------------------------------------------

        batch_orders = (
            db.query(DeliveryOrder)
            .filter(
                DeliveryOrder.batch_id
                == batch.id
            )
            .all()
        )

        batch.total_orders = len(
            batch_orders
        )

        batch.total_tiffins = sum(
            int(
                item.total_tiffins or 0
            )
            for item in batch_orders
        )

        db.add(batch)

        repaired_batches += 1
        repaired_pickups += len(
            pickup_stops
        )

    db.flush()

    return {
        "repaired_batches": repaired_batches,
        "repaired_pickups": repaired_pickups,
    }
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
    repair_result = repair_active_batch_pickups(
        db=db
    )

    drivers = get_eligible_delivery_partners(db)

    if not drivers:
        db.commit()
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
        db.commit()
        return {
            "success": True,
            "message": (
                "No READY delivery orders waiting for assignment"
            ),
            "assigned_orders": 0,
            "assigned_tiffins": 0,
            "batches_created": 0,
            "unassigned_orders": 0,
            "pickup_repair": repair_result,
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

        # --------------------------------------------------------
    # 4. PROCESS EACH DATE + MEAL GROUP
    # --------------------------------------------------------

    for (
        group_date,
        group_meal,
    ), group_orders in groups.items():

        # ====================================================
        # STEP A
        # BUILD GEOGRAPHICAL CLUSTERS
        # ====================================================

        geographical_clusters = (
            build_geographical_clusters(
                group_orders,
                radius_km=CLUSTER_RADIUS_KM,
            )
        )

        # ====================================================
        # PROCESS EACH AREA CLUSTER
        # ====================================================

        for cluster_index, cluster in enumerate(
            geographical_clusters,
            start=1,
        ):

            if not cluster:
                continue

            # =================================================
            # STEP B
            # SPLIT AREA INTO MAX 30 TIFFIN BATCHES
            # =================================================

            cluster_batches = (
                split_cluster_by_tiffin_capacity(
                    cluster,
                    max_tiffins=MAX_TIFFINS_PER_BATCH,
                )
            )

            # =================================================
            # PROCESS EACH 30-TIFFIN BATCH
            # =================================================

            for cluster_batch in cluster_batches:

                if not cluster_batch:
                    continue

                # =================================================
                # STEP C
                # FIND DRIVER NEAREST TO AREA
                # =================================================

                selected_driver = (
                    choose_best_driver_for_cluster(
                        drivers,
                        cluster_batch,
                    )
                )

                if selected_driver is None:
                    continue

                (
                    driver_user,
                    driver_profile,
                    driver_distance,
                ) = selected_driver

                # =================================================
                # STEP D
                # CHECK DRIVER ACTIVE BATCH
                # =================================================

                batch = get_active_batch_for_driver(
                    db=db,
                    driver_id=driver_user.id,
                    delivery_date=group_date,
                    meal_type=group_meal,
                )

                # =================================================
                # CREATE NEW BATCH
                # =================================================

                if batch is None:

                    batch = create_batch(
                        db=db,
                        driver_id=driver_user.id,
                        delivery_date=group_date,
                        meal_type=group_meal,
                    )

                    batches_created_count += 1

                    # Driver becomes busy
                    driver_profile.is_available = False

                    # Driver starting location
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

                    db.flush()

                # =================================================
                # CHECK REMAINING CAPACITY
                # =================================================

                current_tiffins = get_batch_tiffins(
                    db=db,
                    batch_id=batch.id,
                )

                remaining_capacity = (
                    MAX_TIFFINS_PER_BATCH
                    - current_tiffins
                )

                if remaining_capacity <= 0:

                    driver_profile.is_available = False

                    db.add(driver_profile)

                    # Driver removed from current run
                    drivers = [
                        item
                        for item in drivers
                        if item[0].id
                        != driver_user.id
                    ]

                    if not drivers:
                        break

                    continue

                # =================================================
                # STEP E
                # FILTER ORDERS THAT FIT
                # =================================================

                fitting_orders = []

                for item in cluster_batch:

                    delivery_order, order = item

                    quantity = int(
                        delivery_order.total_tiffins
                        or 0
                    )

                    if quantity <= 0:
                        continue

                    if (
                        quantity
                        <= remaining_capacity
                    ):
                        fitting_orders.append(item)

                if not fitting_orders:
                    continue

                # =================================================
                # STEP F
                # OPTIMIZE DELIVERY ROUTE
                # =================================================

                optimized = optimize_order_sequence(
                    driver_profile.current_latitude,
                    driver_profile.current_longitude,
                    fitting_orders,
                )

                if not optimized:
                    continue

                # =================================================
                # STEP G
                # ASSIGN ORDERS
                # =================================================

                batch_current_tiffins = (
                    current_tiffins
                )

                sequence_no = get_next_sequence(
                    db=db,
                    batch_id=batch.id,
                )

                assigned_from_cluster = []

                for (
                    delivery_order,
                    order,
                ) in optimized:

                    quantity = int(
                        delivery_order.total_tiffins
                        or 0
                    )

                    # --------------------------------------------
                    # NEVER EXCEED 30 TIFFINS
                    # --------------------------------------------

                    if (
                        batch_current_tiffins
                        + quantity
                        > MAX_TIFFINS_PER_BATCH
                    ):
                        continue

                    # --------------------------------------------
                    # ASSIGN
                    # --------------------------------------------

                    assign_delivery_order(
                        db=db,
                        delivery_order=delivery_order,
                        batch=batch,
                        sequence_no=sequence_no,
                    )

                    # --------------------------------------------
                    # UPDATE COUNTERS
                    # --------------------------------------------

                    batch_current_tiffins += quantity

                    sequence_no += 1

                    assigned_orders_count += 1

                    assigned_tiffins_count += quantity

                    assigned_from_cluster.append(
                        delivery_order
                    )

                    # --------------------------------------------
                    # RESPONSE DATA
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

                            "cluster_index": (
                                cluster_index
                            ),

                            "cluster_radius_km": (
                                CLUSTER_RADIUS_KM
                            ),

                            "driver_distance_to_cluster_km": (
                                round(
                                    driver_distance,
                                    3,
                                )
                            ),
                        }
                    )

                # =================================================
                # FLUSH
                # =================================================

                db.flush()

                # =================================================
                # RECALCULATE BATCH TOTALS
                # =================================================
                # ============================================================
                # CREATE / UPDATE CHEF-WISE PICKUP STOPS
                # ============================================================
                
                batch_delivery_orders = (
                    db.query(
                        DeliveryOrder,
                        Order,
                    )
                    .join(
                        Order,
                        Order.id == DeliveryOrder.order_id,
                    )
                    .filter(
                        DeliveryOrder.batch_id == batch.id,
                    )
                    .all()
                )
                
                pickup_stops = create_batch_pickup_stops(
                    db=db,
                    batch=batch,
                    delivery_orders=batch_delivery_orders,
                    driver_latitude=batch.start_latitude,
                    driver_longitude=batch.start_longitude,
                )
                
                batch_orders = (
                    db.query(DeliveryOrder)
                    .filter(
                        DeliveryOrder.batch_id
                        == batch.id
                    )
                    .all()
                )

                batch.total_orders = len(
                    batch_orders
                )

                batch.total_tiffins = sum(
                    int(
                        item.total_tiffins
                        or 0
                    )
                    for item in batch_orders
                )

                batch.status = "assigned"

                if not batch.assigned_at:
                    batch.assigned_at = (
                        datetime.utcnow()
                    )

                db.add(batch)

                # =================================================
                # REMOVE ASSIGNED ORDERS FROM CLUSTER
                # =================================================

                assigned_ids = {
                    item.id
                    for item in assigned_from_cluster
                }

                cluster_batch = [
                    item
                    for item in cluster_batch
                    if item[0].id
                    not in assigned_ids
                ]

                # =================================================
                # DRIVER BECOMES BUSY
                # =================================================

                driver_profile.is_available = False

                db.add(driver_profile)

                # =================================================
                # ONE DRIVER = ONE ACTIVE TRIP
                # =================================================

                drivers = [
                    item
                    for item in drivers
                    if item[0].id
                    != driver_user.id
                ]

                if not drivers:
                    break

            if not drivers:
                break

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
        
        "pickup_repair": repair_result,

        "unassigned_orders": (
            unassigned_orders_count
        ),

        "assignments": (
            assignment_results
        ),
    }
    
    
