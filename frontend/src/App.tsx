import { useEffect, useState } from "react";
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

// "" = 全部（走每日任务）；其余为按科目刷题池
const SUBJECTS = ["", "中级会计实务", "财务管理", "经济法"] as const;

function subjectLabel(s: string) {
  return s || "全部科目";
}

export default function App() {
  const [tab, setTab] = useState<Tab>("practice");
  const [subject, setSubject] = useState<string>(
    () => localStorage.getItem("subject") ?? ""
  );
  const [subjectMenuOpen, setSubjectMenuOpen] = useState(false);

  function changeSubject(s: string) {
    setSubject(s);
    localStorage.setItem("subject", s);
    setSubjectMenuOpen(false);
  }

  useEffect(() => {
    if (!subjectMenuOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setSubjectMenuOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [subjectMenuOpen]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__inner">
          <div className="app-header__row">
            <div className="app-brand">
              <div className="app-brand__icon" aria-hidden>📚</div>
              <div className="app-brand__text">
                <span className="app-brand__title">中级会计考试刷题器</span>
              </div>
            </div>
            <div className="app-subject">
              <select
                className="app-subject-select app-subject-select--desktop"
                aria-label="科目筛选"
                value={subject}
                onChange={(e) => changeSubject(e.target.value)}
                title="选择刷题科目"
              >
                {SUBJECTS.map((s) => (
                  <option key={s || "all"} value={s}>
                    {subjectLabel(s)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="app-subject-menu-btn"
                aria-label={`科目：${subjectLabel(subject)}，点击选择`}
                aria-expanded={subjectMenuOpen}
                aria-haspopup="menu"
                onClick={() => setSubjectMenuOpen((open) => !open)}
              >
                <span className="app-subject-menu-btn__icon" aria-hidden>
                  <span />
                  <span />
                  <span />
                </span>
              </button>
              {subjectMenuOpen && (
                <>
                  <button
                    type="button"
                    className="app-subject-backdrop"
                    aria-label="关闭科目菜单"
                    onClick={() => setSubjectMenuOpen(false)}
                  />
                  <div className="app-subject-panel" role="menu" aria-label="科目筛选">
                    <p className="app-subject-panel__title">选择科目</p>
                    {SUBJECTS.map((s) => (
                      <button
                        key={s || "all"}
                        type="button"
                        role="menuitemradio"
                        aria-checked={subject === s}
                        className={`app-subject-panel__item${subject === s ? " app-subject-panel__item--active" : ""}`}
                        onClick={() => changeSubject(s)}
                      >
                        {subjectLabel(s)}
                      </button>
                    ))}
                  </div>
                </>
              )}
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
        {/* 条件渲染：切到某 tab 时重新挂载，useEffect 随之重新拉取后端最新数据，
            避免做完题后错题本/薄弱点仍是切换前的旧数据。各页数据均持久化在后端，
            切走再回来不丢进度。 */}
        <div className="tab-panel">
          {tab === "practice" && <Practice subject={subject} />}
          {tab === "mistakes" && <MistakeBook />}
          {tab === "weakness" && <WeaknessPage />}
          {tab === "upload" && <UploadPage />}
        </div>
      </main>
    </div>
  );
}
