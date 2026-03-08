import { ReactNode } from 'react'
import Navbar from "@/components/layout/Navbar"
import Footer from "@/components/layout/Footer"
import './globals.css'
import { PostHogProvider } from "./providers";

export const metadata = {
  title: 'Snake Bench',
  description: 'Watch AI models compete in Snake battles',
}

export default function RootLayout({
  children,
}: {
  children: ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans min-h-screen flex flex-col bg-gray-50">
        <PostHogProvider>
          <Navbar />
          <main className="flex-1">
            {children}
          </main>
          <Footer />
        </PostHogProvider>
      </body>
    </html>
  )
}
