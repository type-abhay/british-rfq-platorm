"""
Bid submission and deletion routes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import rfq_repository as repo
from app.repositories.rfq_repository import BidNotFoundError, BiddingNotOpenError, RfqNotFoundError
from app.schemas import BidCreate, BidOut

router = APIRouter(prefix="/rfqs/{rfq_id}/bids", tags=["bids"])


@router.post("", response_model=BidOut, status_code=status.HTTP_201_CREATED)
def submit_bid(rfq_id: str, payload: BidCreate, db: Session = Depends(get_db)):
    try:
        bid = repo.submit_bid(db, rfq_id, payload)
    except RfqNotFoundError:
        raise HTTPException(status_code=404, detail="RFQ not found")
    except BiddingNotOpenError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return BidOut.model_validate(bid)


@router.delete("/{bid_id}", status_code=status.HTTP_200_OK)
def delete_bid(rfq_id: str, bid_id: str, db: Session = Depends(get_db)):
    try:
        repo.delete_bid(db, rfq_id=rfq_id, bid_id=bid_id)
    except RfqNotFoundError:
        raise HTTPException(status_code=404, detail="RFQ not found")
    except BidNotFoundError:
        raise HTTPException(status_code=404, detail="Bid not found for this RFQ")
    return {"message": "Bid deleted successfully", "id": bid_id}
