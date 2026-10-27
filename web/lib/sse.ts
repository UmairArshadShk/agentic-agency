export type SseEvent = { event: string; data: unknown };

/**
 * Incremental Server-Sent Events parser. Feed it text chunks as they arrive; it calls
 * onEvent once per complete event (blocks end with a blank line) and buffers the rest.
 */
export function createSseParser(onEvent: (event: SseEvent) => void) {
  let buffer = "";
  return (chunk: string) => {
    buffer += chunk;
    let end = buffer.indexOf("\n\n");
    while (end !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data.push(line.slice(6));
      }
      if (data.length > 0) onEvent({ event, data: JSON.parse(data.join("\n")) });
      end = buffer.indexOf("\n\n");
    }
  };
}
