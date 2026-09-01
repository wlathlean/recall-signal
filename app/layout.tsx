import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  metadataBase: new URL('https://recall-signal-family.metrobill-bl.chatgpt.site'),
  title: 'Recall Signal — Family recall tracker',
  description: 'A practical food, product, pet, and vehicle recall tracker for one family.',
  openGraph: {
    title: 'Recall Signal',
    description: 'Food, product, pet and vehicle recall clarity for your household.',
    type: 'website',
    images: ['/og.png'],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Recall Signal',
    description: 'Food, product, pet and vehicle recall clarity for your household.',
    images: ['/og.png'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
