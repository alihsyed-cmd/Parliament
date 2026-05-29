"use client";

import React from "react";

const PATHS: Record<string, React.ReactNode> = {
  arrow_right: <path d="M5 12h14M13 6l6 6-6 6" />,
  arrow_left: <path d="M19 12H5M11 18l-6-6 6-6" />,
  chevron_right: <path d="M9 6l6 6-6 6" />,
  chevron_down: <path d="M6 9l6 6 6-6" />,
  phone: <path d="M5 4h4l2 5-3 2a12 12 0 006 6l2-3 5 2v4a2 2 0 01-2 2A17 17 0 013 6a2 2 0 012-2z" />,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7l9 6 9-6" /></>,
  link: <><path d="M10 14a4 4 0 005.66 0l3-3a4 4 0 00-5.66-5.66l-1 1" /><path d="M14 10a4 4 0 00-5.66 0l-3 3a4 4 0 005.66 5.66l1-1" /></>,
  map_pin: <><path d="M12 22s7-7.16 7-13a7 7 0 10-14 0c0 5.84 7 13 7 13z" /><circle cx="12" cy="9" r="2.5" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>,
  edit: <path d="M12 20h9M16.5 3.5a2.12 2.12 0 113 3L7 19l-4 1 1-4L16.5 3.5z" />,
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 8h.01M11 12h1v4h1" /></>,
  bell: <><path d="M6 8a6 6 0 1112 0c0 7 3 9 3 9H3s3-2 3-9z" /><path d="M10.3 21a1.94 1.94 0 003.4 0" /></>,
  cal: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 9h18M8 3v4M16 3v4" /></>,
  star: <path d="M12 3l2.9 6 6.6 1-4.8 4.6 1.1 6.6L12 18l-5.9 3.1 1.1-6.6L2.5 10l6.6-1L12 3z" />,
  check: <path d="M5 12l5 5L20 7" />,
  share: <><circle cx="6" cy="12" r="3" /><circle cx="18" cy="6" r="3" /><circle cx="18" cy="18" r="3" /><path d="M9 11l7-4M9 13l7 4" /></>,
};

export function Icon({
  name, size = 18, stroke = 1.6, className, style,
}: {
  name: keyof typeof PATHS | string;
  size?: number; stroke?: number; className?: string; style?: React.CSSProperties;
}) {
  return (
    <svg
      className={className} style={style}
      width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden
    >
      {PATHS[name] ?? null}
    </svg>
  );
}
