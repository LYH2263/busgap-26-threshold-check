from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import Arrival, Line, Trip
from app.services.line_validation import is_valid_line_params

def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Line)) or 0) > 0:
        return
    base = datetime(2026, 9, 17, 7, 0, 0)
    planned, bunch, large = 8.0, 3.0, 15.0
    # 种子三参同样过共用例程，与库约束双向自证
    assert is_valid_line_params(planned, bunch, large)
    line = Line(code="B12", name="城东环线", planned_headway_min=planned,
                bunch_threshold=bunch, large_threshold=large)
    db.add(line); db.flush()
    specs = [("T01", "粤A1001", 0), ("T02", "粤A1002", 2), ("T03", "粤A1003", 18), ("T04", "粤A1004", 26)]
    stops = ["起点站", "市民中心", "火车站", "终点站"]
    for trip_no, vehicle, offset in specs:
        trip = Trip(line_id=line.id, trip_no=trip_no, planned_depart=base + timedelta(minutes=offset), vehicle_no=vehicle)
        db.add(trip); db.flush()
        for seq, stop in enumerate(stops):
            arrive = base + timedelta(minutes=offset + seq * 6)
            if stop == "市民中心" and trip_no == "T02":
                arrive = base + timedelta(minutes=8)
            if stop == "火车站" and trip_no == "T03":
                arrive = base + timedelta(minutes=30)
            db.add(Arrival(trip_id=trip.id, stop_name=stop, stop_seq=seq, actual_arrive=arrive))
    db.commit()
