import { Link, Outlet, Route, Routes } from "react-router-dom";
import styles from "./App.module.css";
import { TopBar } from "./components/TopBar";
import { AskPage } from "./pages/AskPage";
import { BriefPage } from "./pages/BriefPage";
import { MapPage } from "./pages/MapPage";
import { MethodPage } from "./pages/MethodPage";
import { PlanPage } from "./pages/PlanPage";

function Shell() {
  return (
    <div className={styles.shell}>
      <a href="#main" className={styles.skip}>
        Skip to content
      </a>
      <TopBar />
      <main id="main" className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}

function NotFound() {
  return (
    <div className={styles.notFound}>
      <h1>There is no page here.</h1>
      <p>
        Go to the <Link to="/">ward map</Link> to start from all wards.
      </p>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/brief/:wardKey" element={<BriefPage />} />
      <Route element={<Shell />}>
        <Route index element={<MapPage />} />
        <Route path="ask" element={<AskPage />} />
        <Route path="plan" element={<PlanPage />} />
        <Route path="method" element={<MethodPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
