import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

// Grab root element from public/index.html
const root = ReactDOM.createRoot(document.getElementById("root"));

// Render App into root
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);


