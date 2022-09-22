import logging
from tracker_exporter.main import export_cycle_time

logging.getLogger().setLevel(logging.INFO)

def handler(event, context):
    try:
        export_cycle_time(ignore_exceptions=False)
        response = {"statusCode": 200, "message": "success"}
    except Exception as exc:
        response = {"statusCode": 500, "message": exc}
    finally:
        return response
