// Small display helpers shared by the console, the reader and the subtitle list.

const two = (n: number) => String(n).padStart(2, "0");

/** Subtitle time stamps: always HH:MM:SS (PLAN 15.4.5). */
export function clock(seconds: number): string {
  const total = Math.floor(seconds);
  return `${two(Math.floor(total / 3600))}:${two(Math.floor((total % 3600) / 60))}:${two(total % 60)}`;
}

/** Video length: M:SS, or H:MM:SS when there is an hour. */
export function duration(seconds: number | null): string {
  if (seconds == null) return "";
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = `${two(total % 60)}`;
  return hours ? `${hours}:${two(minutes)}:${rest}` : `${minutes}:${rest}`;
}

/** The same links the backend writes into 思维导图.md (mindmap/markdown.py moment_link). */
export function momentLink(platform: string, videoId: string, seconds: number): string {
  const at = Math.floor(seconds);
  if (platform === "bilibili") {
    const [bare] = videoId.split("?");
    const page = /[?&]p=(\d+)/.exec(videoId)?.[1] ?? "1";
    return `https://www.bilibili.com/video/${bare}/?p=${page}&t=${at}`;
  }
  return `https://www.youtube.com/watch?v=${videoId}&t=${at}s`;
}

const SOURCES: Record<string, string> = {
  "youtube-subtitles": "YouTube 人工字幕",
  bcut: "必剪",
  "funasr-onnx": "FunASR",
  "faster-whisper": "Whisper",
};

/** Where the transcript came from (items.transcript_source, PLAN 15.4.4). */
export function sourceLabel(source: string | null): string {
  return source ? (SOURCES[source] ?? source) : "";
}
