import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://varun-astra.sih.gov.in"),
  title: {
    default: "VARUN-ASTRA | Autonomous Marine Oil Spill Intelligence & Vessel Attribution Platform",
    template: "%s | VARUN-ASTRA",
  },
  description:
    "VARUN-ASTRA is an advanced AI-powered marine oil spill intelligence platform integrating Sentinel-1 SAR U-Net neural segmentation, OpenOil hydrodynamic drift simulation, and PostGIS AIS vessel attribution.",
  keywords: [
    "VARUN-ASTRA",
    "Oil Spill Detection",
    "Synthetic Aperture Radar",
    "SAR U-Net",
    "Sentinel-1",
    "OpenOil",
    "Hydrodynamic Particle Drift",
    "AIS Vessel Correlation",
    "Vessel Attribution",
    "Marine Conservation",
    "Smart India Hackathon",
    "SIH-26143",
  ],
  authors: [{ name: "VARUN-ASTRA Team" }],
  creator: "VARUN-ASTRA Team",
  publisher: "VARUN-ASTRA Intelligence Systems",
  openGraph: {
    title: "VARUN-ASTRA | Marine Oil Spill Intelligence Platform",
    description:
      "Autonomous 3-phase oil spill detection, backward drift reconstruction, and vessel attribution platform.",
    url: "https://varun-astra.sih.gov.in",
    siteName: "VARUN-ASTRA",
    images: [
      {
        url: "/ship_oil_spill.jpg",
        width: 1200,
        height: 630,
        alt: "VARUN-ASTRA Telemetry Dashboard",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "VARUN-ASTRA | Marine Oil Spill Intelligence Platform",
    description: "Autonomous 3-phase oil spill detection & AIS vessel attribution.",
    images: ["/ship_oil_spill.jpg"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[#030914] text-slate-100">{children}</body>
    </html>
  );
}
