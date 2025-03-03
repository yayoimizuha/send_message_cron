import asyncio
from base64 import urlsafe_b64encode
from datetime import timedelta, datetime, timezone
from typing import Callable
from firebase_admin import messaging, initialize_app, firestore_async
from firebase_functions import scheduler_fn, options
from google.api_core.datetime_helpers import DatetimeWithNanoseconds
from google.cloud.firestore_v1 import AsyncCollectionReference, FieldFilter

app = initialize_app()
options.set_global_options(region=options.SupportedRegion.ASIA_NORTHEAST1, memory=options.MemoryOption.MB_128)
str2topic: Callable[[str], str] = lambda string: urlsafe_b64encode(string.encode()).decode().replace('=', '')
JST = timezone(offset=timedelta(hours=9), name="JST")


async def run(schedule_time: datetime):
    client = firestore_async.client(app=app, database_id="(default)")
    matched_programs: dict[int, dict[str, set[str] | str | DatetimeWithNanoseconds]] = dict()
    async for cast in client.collection("hello-radiko-data").document("programs").collections():
        cast: AsyncCollectionReference
        value = await (cast
                       .where(filter=FieldFilter("ft", ">", schedule_time + timedelta(minutes=10)))
                       .where(filter=FieldFilter("ft", "<", schedule_time + timedelta(minutes=15)))).get()
        for doc in value:
            print(cast.id)
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
    if messages.__len__()!=0:
        messaging.send_each(messages)


@scheduler_fn.on_schedule(schedule="*/5 * * * *")
def runner(event: scheduler_fn.ScheduledEvent):
    asyncio.run(run(event.schedule_time))


# asyncio.run(run(datetime(year=2025, month=2, day=17, hour=0, minute=17,tzinfo=JST)))
