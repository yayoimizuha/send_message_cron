from base64 import urlsafe_b64encode
from datetime import timedelta, datetime, timezone
from typing import Callable
from firebase_admin import messaging, initialize_app, firestore
from firebase_functions import scheduler_fn, options
from google.api_core.datetime_helpers import DatetimeWithNanoseconds
from google.cloud.firestore_v1 import FieldFilter, CollectionReference

app = initialize_app()
options.set_global_options(region=options.SupportedRegion.ASIA_NORTHEAST1, memory=options.MemoryOption.MB_256,
                           timeout_sec=15)
str2topic: Callable[[str], str] = lambda string: urlsafe_b64encode(string.encode()).decode().replace('=', '')
JST = timezone(offset=timedelta(hours=9), name="JST")


def run(schedule_time: datetime):
    print(f"{schedule_time=}")
    client = firestore.client(app=app, database_id="(default)")
    matched_programs: dict[int, dict[str, set[str] | str | DatetimeWithNanoseconds]] = dict()
    for cast in client.collection("hello-radiko-data").document("programs").collections():
        cast: CollectionReference
        value = (cast
                 .where(filter=FieldFilter("ft", ">", schedule_time + timedelta(minutes=10)))
                 .where(filter=FieldFilter("ft", "<=", schedule_time + timedelta(minutes=15)))).get()
        for doc in value:
            print(f"{cast.id=}")
            print(doc.to_dict())
            if int(doc.id) in matched_programs.keys():
                matched_programs[int(doc.id)]["target"].add(cast.id)
            else:
                matched_programs[int(doc.id)] = {
                    "target": {cast.id},
                    "title": doc.get("title"),
                    "ft": doc.get("ft")
                }

    messages: list[messaging.Message] = []
    for v in matched_programs.values():
        messages.append(messaging.Message(data={
            "target": ",".join(v["target"]),
            "title": v["title"],
            "ft": v["ft"].astimezone(JST).strftime("%m月%d日 %H時%M分")
        }, topic=str2topic("notify")))
    for message in messages:
        print(message.data)
    if messages.__len__() != 0:
        messaging.send_each(messages)


@scheduler_fn.on_schedule(schedule="*/5 * * * *")
def runner(event: scheduler_fn.ScheduledEvent):
    run(event.schedule_time.astimezone(JST))
# try:
#     loop = asyncio.get_running_loop()
# except RuntimeError:
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
# loop.run_until_complete(run(event.schedule_time))

# run(datetime(year=2025, month=2, day=17, hour=0, minute=17,tzinfo=JST))
