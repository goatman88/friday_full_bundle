import React from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider, Link } from 'react-router-dom'
import App from './pages/App.jsx'
import MultiUploader from './pages/MultiUploader.jsx'

const router = createBrowserRouter([
  { path: '/', element: <App /> },
  { path: '/multi-uploader', element: <MultiUploader /> },
])

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
)
