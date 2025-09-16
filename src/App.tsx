import CrawlUploadWithStatus from "./components/CrawlUploadWithStatus";
import MultiUploaderWithStatus from "./components/MultiUploaderWithStatus";

export default function App() {
  return (
    <main style={{ padding: 20 }}>
      <CrawlUploadWithStatus />
      <hr />
      <MultiUploaderWithStatus />
    </main>
  );
}

"use client";
import CrawlUploadWithStatus from "@/components/CrawlUploadWithStatus";
import MultiUploaderWithStatus from "@/components/MultiUploaderWithStatus";

export default function Page() {
  return (
    <main style={{ padding: 20 }}>
      <CrawlUploadWithStatus />
      <hr />
      <MultiUploaderWithStatus />
    </main>
  );
}
