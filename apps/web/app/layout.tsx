import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {title: "RoadPulse AI | Traffic Intelligence", description: "Local traffic analysis powered by YOLOX and ByteTrack"};
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}
