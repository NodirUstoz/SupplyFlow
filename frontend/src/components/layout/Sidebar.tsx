import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  badge?: number;
  children?: NavItem[];
}

interface SidebarProps {
  items: NavItem[];
  isCollapsed?: boolean;
  onToggle?: () => void;
  logo?: string;
}

const Sidebar: React.FC<SidebarProps> = ({ items, isCollapsed = false, onToggle, logo = 'Platform' }) => {
  const location = useLocation();
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const toggleGroup = (path: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  };

  return (
    <aside className={`fixed left-0 top-0 h-full bg-white border-r border-gray-200 z-40 transition-all duration-300 ${isCollapsed ? 'w-16' : 'w-64'}`}>
      <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
        {!isCollapsed && <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">{logo}</span>}
        <button onClick={onToggle} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500" aria-label="Toggle sidebar">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={isCollapsed ? 'M13 5l7 7-7 7M5 5l7 7-7 7' : 'M11 19l-7-7 7-7M19 19l-7-7 7-7'} />
          </svg>
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {items.map(item => (
          <div key={item.path}>
            {item.children ? (
              <>
                <button onClick={() => toggleGroup(item.path)}
                  className={`w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors
                    ${location.pathname.startsWith(item.path) ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-100'}`}>
                  <span className="text-lg mr-3">{item.icon}</span>
                  {!isCollapsed && <>
                    <span className="flex-1 text-left">{item.label}</span>
                    <svg className={`w-4 h-4 transition-transform ${expandedGroups.has(item.path) ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </>}
                </button>
                {!isCollapsed && expandedGroups.has(item.path) && (
                  <div className="ml-8 mt-1 space-y-1">
                    {item.children.map(child => (
                      <NavLink key={child.path} to={child.path}
                        className={({ isActive }) => `block px-3 py-2 text-sm rounded-lg transition-colors ${isActive ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-50'}`}>
                        {child.label}
                      </NavLink>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <NavLink to={item.path}
                className={({ isActive }) => `flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-100'}`}>
                <span className="text-lg mr-3">{item.icon}</span>
                {!isCollapsed && <>
                  <span className="flex-1">{item.label}</span>
                  {item.badge !== undefined && item.badge > 0 && (
                    <span className="ml-auto w-5 h-5 text-xs font-bold text-white bg-red-500 rounded-full flex items-center justify-center">
                      {item.badge > 99 ? '99+' : item.badge}
                    </span>
                  )}
                </>}
              </NavLink>
            )}
          </div>
        ))}
      </nav>
      <div className="border-t border-gray-200 p-4">
        <NavLink to="/settings" className="flex items-center px-3 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100">
          <span className="mr-3">Settings</span>
        </NavLink>
      </div>
    </aside>
  );
};

export default Sidebar;
