import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking...");

  useEffect(() => {
    async function checkBackend() {
      try {
        const response = await fetch("http://127.0.0.1:8000/health");

        if (!response.ok) {
          throw new Error("Backend returned an error");
        }

        const data = await response.json();
        setBackendStatus(data.status);
      } catch (error) {
        console.error(error);
        setBackendStatus("offline");
      }
    }

    checkBackend();
  }, []);

  return (
    <main>
      <h1>Data Agent</h1>
      <p>
        Backend status: <strong>{backendStatus}</strong>
      </p>
    </main>
  );
}

export default App;