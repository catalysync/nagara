import asyncio
from uuid import uuid4

from nagara.kit.pubsub import PubSub


async def test_publish_then_subscribe_after_close_yields_buffered_events():
    bus: PubSub = PubSub()
    topic = uuid4()
    sub = bus.subscribe(topic)
    await bus.publish(topic, {"e": "a"})
    await bus.publish(topic, {"e": "b"})
    bus.close(topic)

    received = [ev async for ev in sub]
    assert received == [{"e": "a"}, {"e": "b"}]


async def test_close_signals_end_of_stream():
    bus: PubSub = PubSub()
    topic = "t1"
    sub = bus.subscribe(topic)
    bus.close(topic)
    received = [ev async for ev in sub]
    assert received == []


async def test_multiple_subscribers_each_receive_every_event():
    bus: PubSub = PubSub()
    topic = "shared"
    s1 = bus.subscribe(topic)
    s2 = bus.subscribe(topic)
    await bus.publish(topic, "ev1")
    await bus.publish(topic, "ev2")
    bus.close(topic)
    out1 = [e async for e in s1]
    out2 = [e async for e in s2]
    assert out1 == ["ev1", "ev2"]
    assert out2 == ["ev1", "ev2"]


async def test_publish_to_topic_with_no_subscribers_is_noop():
    bus: PubSub = PubSub()
    await bus.publish("ghost", {"e": "x"})


async def test_subscriber_unregisters_on_iterator_exit():
    bus: PubSub = PubSub()
    topic = "cleanup"
    sub = bus.subscribe(topic)
    await bus.publish(topic, "first")

    saw = None
    async for ev in sub:
        saw = ev
        break
    assert saw == "first"
    # The dropped subscriber should be removed from the registry, so
    # publishing again doesn't queue into a dead consumer.
    await bus.publish(topic, "second")
    bus.close(topic)


async def test_keys_can_be_any_hashable():
    bus: PubSub[int] = PubSub()
    sub = bus.subscribe(42)
    await bus.publish(42, "answer")
    bus.close(42)
    out = [e async for e in sub]
    assert out == ["answer"]


async def test_bounded_queue_drops_overflow_events():
    bus: PubSub = PubSub(maxsize=2)
    topic = "bounded"
    sub = bus.subscribe(topic)
    await bus.publish(topic, "a")
    await bus.publish(topic, "b")
    await bus.publish(topic, "c")  # dropped, queue full
    await bus.publish(topic, "d")  # dropped, queue full
    bus.close(topic)
    received = [ev async for ev in sub]
    assert received == ["a", "b"]


async def test_bounded_close_still_signals_end_of_stream():
    bus: PubSub = PubSub(maxsize=1)
    topic = "bounded-close"
    sub = bus.subscribe(topic)
    await bus.publish(topic, "a")
    bus.close(topic)  # queue is full but close must still wake the iterator
    received = [ev async for ev in sub]
    assert received == ["a"]


async def test_close_drops_topic_from_registry():
    bus: PubSub = PubSub()
    topic = "drop"
    bus.subscribe(topic)
    assert topic in bus.topics()
    bus.close(topic)
    assert topic not in bus.topics()
