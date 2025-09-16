import CrawlUpload from "./components/CrawlUpload";
import MultiUploader from "./components/MultiUploader";

export default function App() {
  return (
    <main style={{ padding: 20 }}>
      <CrawlUpload />
      <hr />
      <MultiUploader />
    </main>
  );
}

