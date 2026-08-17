"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import "./globals.css";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (pathname === "/login") return;
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }

    // Verify token is still valid
    fetch(`${API}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(r => {
      if (!r.ok) {
        localStorage.removeItem("token");
        localStorage.removeItem("username");
        router.push("/login");
      }
    }).catch(() => {
      // If backend unreachable, don't log out — just let it be
    });
  }, [pathname]);

  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
