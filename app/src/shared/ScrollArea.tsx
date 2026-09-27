import { type ReactNode, type Ref, useEffect, useImperativeHandle, useRef } from "react";

import { watchScrollIdle } from "./scrollIdle";

/** A scrolling region with the floating scrollbar (PLAN 15.4.5). */
export function ScrollArea({ children, className = "", label, ref }: {
  children: ReactNode;
  className?: string;
  label?: string;
  ref?: Ref<HTMLDivElement | null>;
}) {
  const own = useRef<HTMLDivElement>(null);
  useImperativeHandle(ref, () => own.current as HTMLDivElement, []);
  useEffect(() => (own.current ? watchScrollIdle(own.current) : undefined), []);
  return (
    <div ref={own} className={`scroll ${className}`} aria-label={label}>
      {children}
    </div>
  );
}
