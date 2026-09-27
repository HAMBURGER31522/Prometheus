// Liquid-glass lens (direction C, D-29): an SVG displacement filter whose map is drawn
// to the exact size of the glass element, so the rim bends what is behind it. Used by
// `backdrop-filter: url(#id)` on the sidebar capsule and the reader toolbar only.
import { type RefObject, useEffect, useRef } from "react";

function drawMap(width: number, height: number, radius: number, bezel: number): string | null {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return null; // jsdom
  const image = context.createImageData(width, height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const qx = Math.max(Math.abs(x - width / 2) - (width / 2 - radius), 0);
      const qy = Math.max(Math.abs(y - height / 2) - (height / 2 - radius), 0);
      const outside = Math.hypot(qx, qy) - radius; // signed distance to the rounded rect
      const inside = Math.max(0, -Math.max(Math.abs(x - width / 2) - width / 2, Math.abs(y - height / 2) - height / 2, outside));
      const t = Math.min(1, inside / bezel);
      const bend = (1 - t) * (1 - t); // strongest right at the rim
      const i = (y * width + x) * 4;
      image.data[i] = 128 + ((width / 2 - x) / (width / 2)) * bend * 127;
      image.data[i + 1] = 128 + ((height / 2 - y) / (height / 2)) * bend * 127;
      image.data[i + 2] = 128;
      image.data[i + 3] = 255;
    }
  }
  context.putImageData(image, 0, 0);
  return canvas.toDataURL();
}

export function Lens({ id, target, radius, bezel, scale }: {
  id: string;
  target: RefObject<HTMLElement | null>;
  radius: number;
  bezel: number;
  scale: number;
}) {
  const image = useRef<SVGFEImageElement>(null);
  useEffect(() => {
    const element = target.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const paint = () => {
      const width = Math.round(element.offsetWidth);
      const height = Math.round(element.offsetHeight);
      const map = width && height ? drawMap(width, height, radius, bezel) : null;
      if (!map || !image.current) return;
      image.current.setAttribute("href", map);
      image.current.setAttribute("width", String(width));
      image.current.setAttribute("height", String(height));
    };
    // Repaint once a resize settles (the rail animates its width), not on every frame.
    let timer: ReturnType<typeof setTimeout> | undefined;
    const observer = new ResizeObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(paint, 120);
    });
    observer.observe(element);
    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [target, radius, bezel]);
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true">
      <filter id={id} x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
        <feImage ref={image} x="0" y="0" width="1" height="1" result="map" preserveAspectRatio="none" />
        <feDisplacementMap in="SourceGraphic" in2="map" scale={scale} xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </svg>
  );
}
