
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.explore_product import ExploreProduct
from app.models.user import User
from app.schemas.explore import (
    EXPLORE_CATEGORIES,
    ExploreProductCreate,
    ExploreProductUpdate,
    ExploreProductResponse,
    ExploreCategoryResponse,
)

import cloudinary.uploader

router = APIRouter(prefix="/explore", tags=["Explore"])


def require_chef(current_user: User):
    if current_user.role != "chef":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only chefs can manage Explore products",
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive",
        )


def upload_explore_image(image: UploadFile) -> str:
    """Upload an Explore product image to Cloudinary."""
    try:
        result = cloudinary.uploader.upload(
            image.file,
            folder="explore_products",
            resource_type="image",
            quality="auto",
            fetch_format="auto",
            transformation=[
                {
                    "width": 800,
                    "height": 800,
                    "crop": "limit",
                }
            ],
        )
        return result["secure_url"]

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Explore product image upload failed",
        ) from exc


def validate_create_data(
    name: str,
    description: str | None,
    category: str,
    price: float,
    quantity: int,
    image_url: str | None,
) -> ExploreProductCreate:
    try:
        return ExploreProductCreate.model_validate(
            {
                "name": name,
                "description": description,
                "category": category,
                "price": price,
                "quantity": quantity,
                "image_url": image_url,
            }
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(include_url=False),
        ) from exc


@router.get(
    "/categories",
    response_model=list[ExploreCategoryResponse],
)
def get_explore_categories(
    db: Session = Depends(get_db),
):
    products = (
        db.query(ExploreProduct.category)
        .filter(ExploreProduct.is_active.is_(True))
        .all()
    )

    counts = {}
    for (category,) in products:
        counts[category] = counts.get(category, 0) + 1

    return [
        {
            "name": category,
            "product_count": counts.get(category, 0),
        }
        for category in EXPLORE_CATEGORIES
    ]


@router.get(
    "/products",
    response_model=list[ExploreProductResponse],
)
def get_explore_products(
    category: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(ExploreProduct).filter(
        ExploreProduct.is_active.is_(True),
        ExploreProduct.quantity > 0,
    )

    if category:
        normalized_category = next(
            (
                item
                for item in EXPLORE_CATEGORIES
                if item.casefold() == category.strip().casefold()
            ),
            None,
        )

        if normalized_category is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Explore category",
            )

        query = query.filter(
            ExploreProduct.category == normalized_category
        )

    return (
        query.order_by(ExploreProduct.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get(
    "/products/mine",
    response_model=list[ExploreProductResponse],
)
def get_my_explore_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_chef(current_user)

    return (
        db.query(ExploreProduct)
        .filter(ExploreProduct.chef_id == current_user.id)
        .order_by(ExploreProduct.created_at.desc())
        .all()
    )


@router.post(
    "/products",
    response_model=ExploreProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_explore_product(
    name: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    quantity: int = Form(...),
    description: str | None = Form(default=None),
    image_url: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_chef(current_user)

    product_data = validate_create_data(
        name=name,
        description=description,
        category=category,
        price=price,
        quantity=quantity,
        image_url=image_url,
    )

    final_image_url = product_data.image_url

    if image is not None and image.filename:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload a valid image file",
            )

        final_image_url = upload_explore_image(image)

    product = ExploreProduct(
        chef_id=current_user.id,
        name=product_data.name.strip(),
        description=product_data.description,
        category=product_data.category,
        price=product_data.price,
        image_url=final_image_url,
        quantity=product_data.quantity,
        is_active=True,
    )

    try:
        db.add(product)
        db.commit()
        db.refresh(product)
    except Exception:
        db.rollback()
        raise

    return product


@router.put(
    "/products/{product_id}",
    response_model=ExploreProductResponse,
)
def update_explore_product(
    product_id: UUID,
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    category: str | None = Form(default=None),
    price: float | None = Form(default=None),
    quantity: int | None = Form(default=None),
    is_active: bool | None = Form(default=None),
    image_url: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_chef(current_user)

    product = (
        db.query(ExploreProduct)
        .filter(
            ExploreProduct.id == product_id,
            ExploreProduct.chef_id == current_user.id,
        )
        .first()
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Explore product not found",
        )

    update_data = {}

    if name is not None:
        update_data["name"] = name

    if description is not None:
        update_data["description"] = description

    if category is not None:
        update_data["category"] = category

    if price is not None:
        update_data["price"] = price

    if quantity is not None:
        update_data["quantity"] = quantity

    if is_active is not None:
        update_data["is_active"] = is_active

    try:
        validated_data = ExploreProductUpdate.model_validate(update_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(include_url=False),
        ) from exc

    for field, value in validated_data.model_dump(
        exclude_unset=True
    ).items():
        if field == "name" and value is not None:
            value = value.strip()
        setattr(product, field, value)

    if image is not None and image.filename:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload a valid image file",
            )

        product.image_url = upload_explore_image(image)
    elif image_url is not None:
        product.image_url = image_url

    try:
        db.commit()
        db.refresh(product)
    except Exception:
        db.rollback()
        raise

    return product


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_200_OK,
)
def deactivate_explore_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_chef(current_user)

    product = (
        db.query(ExploreProduct)
        .filter(
            ExploreProduct.id == product_id,
            ExploreProduct.chef_id == current_user.id,
        )
        .first()
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Explore product not found",
        )

    product.is_active = False
    db.commit()

    return {
        "message": "Explore product deactivated successfully",
        "product_id": str(product.id),
    }
