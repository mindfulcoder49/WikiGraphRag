import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import Build from './pages/Build'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/build/:buildId" element={<Build />} />
      </Routes>
    </BrowserRouter>
  )
}
