import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark";
const ThemeContext = createContext<{ theme: Theme; toggle: () => void } | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => localStorage.getItem("mm.owner.theme") === "light" ? "light" : "dark");
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("mm.owner.theme", theme);
  }, [theme]);
  const value = useMemo(() => ({ theme, toggle: () => setTheme((current) => current === "dark" ? "light" : "dark") }), [theme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function ThemeToggle() {
  const value = useContext(ThemeContext);
  if (!value) return null;
  return <button className="icon-button" onClick={value.toggle} aria-label={`Use ${value.theme === "dark" ? "light" : "dark"} theme`}>
    {value.theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
  </button>;
}
