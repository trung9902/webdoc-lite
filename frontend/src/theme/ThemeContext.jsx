import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const ThemeContext = createContext(null);

/** Bốn giao diện người dùng đổi được ở menu tài khoản. Mặc định "redlight" (đỏ rượu). */
const THEMES = {
  light: {
    themeSidebar: 'light', header: '#FFFFFF', frame: '#E6F7FF', sidebar: '#FFFFFF', menu: '#FFFFFF',
    text: '#000000', sidebarText: '#000000', textContrast: '#000000', linkText: '#0b7ced', buttonPrimary: '#0b7ced',
  },
  dark: {
    themeSidebar: 'dark', header: '#0e0e0e', frame: '#000000', sidebar: '#000000', menu: '#0e0e0e',
    text: '#d1d1d1', sidebarText: '#d1d1d1', textContrast: '#d1d1d1', linkText: '#FFFFFF', buttonPrimary: '#0b7ced',
  },
  olive: {
    themeSidebar: 'light', header: '#2e371d', frame: '#5a0000', sidebar: '#fffbf2', menu: '#fffbf2',
    text: '#000000', sidebarText: '#000000', textContrast: '#999999', linkText: '#516d1c', buttonPrimary: '#0b7ced',
  },
  redlight: {
    themeSidebar: 'light', header: 'rgb(139, 7, 9)', frame: '#ca0c0e', sidebar: '#8b070a', menu: '#8b070a',
    text: '#000000', sidebarText: '#ffffff', textContrast: '#999999', linkText: '#ffffff', buttonPrimary: '#ca0c0e',
  },
};

const read = () => {
  try {
    const saved = localStorage.getItem('theme');

    return THEMES[saved] ? saved : 'redlight';
  } catch {
    return 'redlight';
  }
};

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(read);
  const colors = THEMES[theme];

  const changeTheme = useCallback((name) => {
    if (!THEMES[name]) return;
    setTheme(name);
    try {
      localStorage.setItem('theme', name);
    } catch {
      /* không lưu được thì vẫn đổi cho phiên này */
    }
  }, []);

  // CSS thuần (global.css) đọc màu sidebar qua biến.
  useEffect(() => {
    const root = document.documentElement.style;

    root.setProperty('--sidebar-bg', colors.sidebar);
    root.setProperty('--sidebar-text', colors.sidebarText);
  }, [colors]);

  const value = useMemo(() => ({ theme, colors, changeTheme }), [theme, colors, changeTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useTheme = () => useContext(ThemeContext);
