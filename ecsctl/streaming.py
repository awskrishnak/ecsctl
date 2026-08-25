import time


def stream_log_events(logs_client, log_group, log_stream, start_time=None):
    next_token = None
    while True:
        kwargs = {
            "logGroupName": log_group,
            "logStreamName": log_stream,
            "startFromHead": False,
        }
        if next_token:
            kwargs["nextToken"] = next_token
        if start_time:
            kwargs["startTime"] = start_time
            start_time = None

        resp = logs_client.get_log_events(**kwargs)
        events = resp.get("events", [])
        for event in events:
            yield event

        new_token = resp.get("nextForwardToken")
        if new_token == next_token or not events:
            time.sleep(1)
        next_token = new_token
