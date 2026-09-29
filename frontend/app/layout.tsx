import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Skill Gap Training",
  description: "Mapeia skills de mini CVs e recomenda treinamentos FY27",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
