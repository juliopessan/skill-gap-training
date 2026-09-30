import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Inter_Tight, Instrument_Serif } from "next/font/google";
import Providers from "@/components/Providers";
import { BRAND_COLORS } from "@/lib/brand";
import "./globals.css";

const display = Inter_Tight({ subsets: ["latin"], weight: ["700", "800"], variable: "--f-display", display: "swap" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--f-mono", display: "swap" });
const voice = Instrument_Serif({ subsets: ["latin"], weight: "400", style: "italic", variable: "--f-voice", display: "swap" });

export const metadata: Metadata = {
  applicationName: "Skill Gap Training",
  title: "Skill Gap Training",
  description: "Mapeia skills de mini CVs e recomenda treinamentos FY27",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: BRAND_COLORS.light.paper },
    { media: "(prefers-color-scheme: dark)", color: BRAND_COLORS.dark.paper },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${display.variable} ${mono.variable} ${voice.variable}`}>
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
