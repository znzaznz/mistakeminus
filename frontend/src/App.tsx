import { useState } from "react";
import Practice from "./Practice";
import MistakeBook from "./MistakeBook";
import WeaknessPage from "./WeaknessPage";
import UploadPage from "./UploadPage";

type Tab = "practice" | "mistakes" | "weakness" | "upload";

const TABS: { id: Tab; label: string }[] = [
  { id: "practice", label: "刷题" },
  { id: "mistakes", label: "错题本" },
  { id: "weakness", label: "薄弱点" },
  { id: "upload", label: "上传" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("practice");

  return (
    <>
      <header className="app-header">
        <div className="app-header__inner">
          <div className="app-brand">
            <div className="app-brand__icon" aria-hidden>📚</div>
            <div className="app-brand__text">
              <span className="app-brand__title">中级会计考试刷题器</span>
              <span className="app-brand__subtitle">经济法 · 智能复习</span>
            </div>
          </div>
          <nav className="app-nav" aria-label="主导航">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={`app-nav__btn${tab === t.id ? " app-nav__btn--active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="app-main">
        <div className="tab-panel" hidden={tab !== "practice"}>
          <Practice />
        </div>
        <div className="tab-panel" hidden={tab !== "mistakes"}>
          <MistakeBook />
        </div>
        <div className="tab-panel" hidden={tab !== "weakness"}>
          <WeaknessPage />
        </div>
        <div className="tab-panel" hidden={tab !== "upload"}>
          <UploadPage />
        </div>
      </main>
    </>
  );
}
