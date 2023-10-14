import logging
from tracker_exporter import run_etl

logging.getLogger().setLevel(logging.INFO)


def handler(event, context):
    try:
        run_etl(ignore_exceptions=False)
        response = {"statusCode": 200, "message": "success"}
    except Exception as exc:
        response = {"statusCode": 500, "message": exc}
    finally:
        return response
