import { describe, expect, it } from "vitest";
import { createSseParser, type SseEvent } from "./sse";

function collect() {
  const events: SseEvent[] = [];
  return { events, feed: createSseParser((e) => events.push(e)) };
}

describe("createSseParser", () => {
  it("parses a complete event", () => {
    const { events, feed } = collect();
    feed('event: token\ndata: {"text": "hi "}\n\n');
    expect(events).toEqual([{ event: "token", data: { text: "hi " } }]);
  });

  it("parses several events in one chunk, in order", () => {
    const { events, feed } = collect();
    feed('event: token\ndata: {"text": "a"}\n\nevent: done\ndata: {}\n\n');
    expect(events.map((e) => e.event)).toEqual(["token", "done"]);
  });

  it("waits for the rest of an event split across chunks", () => {
    const { events, feed } = collect();
    feed('event: token\ndata: {"te');
    expect(events).toEqual([]);
    feed('xt": "split"}\n');
    expect(events).toEqual([]);
    feed("\n");
    expect(events).toEqual([{ event: "token", data: { text: "split" } }]);
  });

  it("keeps an incomplete trailing event buffered", () => {
    const { events, feed } = collect();
    feed('event: token\ndata: {"text": "a"}\n\nevent: tok');
    expect(events).toHaveLength(1);
    feed('en\ndata: {"text": "b"}\n\n');
    expect(events).toHaveLength(2);
  });

  it("defaults the event name and ignores blocks without data", () => {
    const { events, feed } = collect();
    feed(': comment\n\ndata: {"x": 1}\n\n');
    expect(events).toEqual([{ event: "message", data: { x: 1 } }]);
  });
});
