import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { 
  Calendar, 
  Upload, 
  Users, 
  MapPin, 
  Briefcase, 
  CheckCircle2, 
  AlertCircle, 
  Menu, 
  X, 
  ChevronLeft, 
  ChevronRight,
  ChevronDown,
  Check,
  Download,
  Trash2,
  Edit2,
  Search,
  UserPlus,
  UserMinus,
  Clock,
  Tag,
  Loader2,
  Info,
  LayoutList,
  Grid3X3,
  Filter,
  Plus,
  CheckSquare,
  Square,
  LogOut,
  RotateCcw
} from 'lucide-react';

import './index.css';

// --- 全局配置 ---
const API_BASE = (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'))
  ? 'http://localhost:3000/api'
  : '/api';

const getJwtExp = (token: string): number | null => {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const payloadBase64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = payloadBase64.padEnd(payloadBase64.length + ((4 - (payloadBase64.length % 4)) % 4), '=');
    const json = atob(padded);
    const payload = JSON.parse(json);
    const exp = payload?.exp;
    return typeof exp === 'number' ? exp : null;
  } catch {
    return null;
  }
};

// --- 类型定义 ---
interface User {
  id: number;
  name: string;
  phone: string;
  role: 'admin' | 'user';
  token: string;
}

interface ManagedUser {
  id: number;
  name: string;
  phone: string;
  role: string;
  status: number;
  created_at: string;
}

interface Store {
  id: string;
  name: string;
  brand: string;
  province: string;
  city: string;
  assignedExpert: string; 
  specialRequirements?: string;
  monthlyFrequency: number; 
  importStatus?: string; // 新增字段
  deletedAt?: string | null;
  serviceStartMonth?: string | null;
  serviceResumeMonth?: string | null;
}

interface Visit {
  id: string;
  storeId: string;
  date: string; 
  expertName: string;
  status: 'planned' | 'completed';
  type?: 'regular' | 'extra';
  title?: string;
  countTowardsTarget?: boolean;
  createdBy?: number | null;
  createdAt?: string | null;
}

interface ToastMsg {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface MultiSelectProps {
  label: string;
  options: string[];
  value: string[];
  onChange: (val: string[]) => void;
}

const MultiSelect: React.FC<MultiSelectProps> = ({ label, options, value, onChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [wrapperRef]);

  const handleSelect = (option: string, e: React.MouseEvent) => {
    e.stopPropagation();
    let newValue: string[];
    if (option === '全部') {
      newValue = ['全部'];
    } else {
      if (value.includes('全部')) {
        newValue = [option];
      } else {
        if (value.includes(option)) {
          newValue = value.filter(v => v !== option);
          if (newValue.length === 0) newValue = ['全部'];
        } else {
          newValue = [...value, option];
        }
      }
    }
    onChange(newValue);
  };

  const displayValue = value.includes('全部') 
    ? '全部' 
    : value.length === 1 
      ? value[0] 
      : `已选 ${value.length} 项`;

  return (
    <div className="relative" ref={wrapperRef}>
      <div className="flex flex-col gap-1 min-w-[140px] relative z-20">
        <span className="text-[10px] text-gray-400 font-bold uppercase">{label}</span>
        <button 
          onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
          className="p-2 border rounded text-sm bg-white text-left flex justify-between items-center w-full"
        >
          <span className="truncate max-w-[100px]">{displayValue}</span>
          <ChevronDown size={14} className="text-gray-400 flex-shrink-0 ml-1"/>
        </button>
      </div>
      
      {isOpen && (
        <div 
          className="absolute top-full left-0 mt-1 w-full min-w-[200px] max-h-60 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg z-50 p-1"
          onClick={(e) => e.stopPropagation()} // 阻止冒泡到父级可能的点击监听
        >
          {options.map(opt => (
            <div 
              key={opt}
              onClick={(e) => handleSelect(opt, e)}
              className={`flex items-center gap-2 p-2 rounded cursor-pointer text-sm ${value.includes(opt) ? 'bg-blue-50 text-blue-600 font-medium' : 'hover:bg-gray-50'}`}
            >
              <div className={`w-4 h-4 border rounded flex items-center justify-center flex-shrink-0 ${value.includes(opt) ? 'bg-blue-600 border-blue-600' : 'border-gray-300'}`}>
                {value.includes(opt) && <Check size={10} className="text-white"/>}
              </div>
              <span className="truncate">{opt}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default function App() {
  // 状态管理
  const [activeTab, setActiveTab] = useState<'calendar' | 'admin'>('calendar');
  const [currentUser, setCurrentUser] = useState<string>(''); 
  const [viewMode, setViewMode] = useState<'month' | 'week'>('week');

  // Auth 状态
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('auth_user');
    if (!saved) return null;
    try {
      const parsed = JSON.parse(saved);
      const token = parsed?.token;
      if (typeof token === 'string') {
        const exp = getJwtExp(token);
        if (exp && exp * 1000 <= Date.now()) {
          localStorage.removeItem('auth_user');
          sessionStorage.setItem('auth_session_expired', '1');
          return null;
        }
      }
      return parsed;
    } catch {
      localStorage.removeItem('auth_user');
      return null;
    }
  });
  const [authFormData, setAuthFormData] = useState({ phone: '', password: '' });
  
  // 管理员账号管理状态
  const [managedUsers, setManagedUsers] = useState<ManagedUser[]>([]);
  const [showUserModal, setShowUserModal] = useState(false);
  const [editingUser, setEditingUser] = useState<Partial<ManagedUser & { password?: string }> | null>(null);

  // 数据状态
  const [experts, setExperts] = useState<string[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [visits, setVisits] = useState<Visit[]>([]);
  
  // 批量操作状态
  const [selectedStoreIds, setSelectedStoreIds] = useState<string[]>([]);

  // UI 状态
  const [isLoading, setIsLoading] = useState(true);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDateForVisit, setSelectedDateForVisit] = useState<string | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastMsg[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [dragging, setDragging] = useState<{ kind: 'store' | 'visit'; id: string } | null>(null);
  const [dragHoverDate, setDragHoverDate] = useState<string | null>(null);
  const [dropFlashDate, setDropFlashDate] = useState<string | null>(null);
  const [touchDrag, setTouchDrag] = useState<{
    visitId: string;
    label: string;
    x: number;
    y: number;
    originDate: string;
  } | null>(null);
  const dragOverLastTsRef = useRef(0);
  const dropFlashTimerRef = useRef<number | null>(null);
  const touchLongPressTimerRef = useRef<number | null>(null);
  const touchStartPointRef = useRef<{ x: number; y: number } | null>(null);
  const dragHoverDateRef = useRef<string | null>(null);
  const touchDragRef = useRef<typeof touchDrag>(null);
  const lastTouchDragEndRef = useRef(0);
  
  // 编辑/导入/筛选状态
  const [csvText, setCsvText] = useState('');
  const [editingStore, setEditingStore] = useState<Store | null>(null); 
  // const [newExpertName, setNewExpertName] = useState(''); // 已移除
  const [adminFilterCity, setAdminFilterCity] = useState<string[]>(['全部']);
  const [adminFilterBrand, setAdminFilterBrand] = useState<string[]>(['全部']);
  const [adminFilterProvince, setAdminFilterProvince] = useState<string[]>(['全部']);
  const [adminFilterExpert, setAdminFilterExpert] = useState<string[]>(['全部']);
  const [adminFilterImportStatus, setAdminFilterImportStatus] = useState('否'); // 默认显示未导入门店
  const [adminFilterSpecialRequirements, setAdminFilterSpecialRequirements] = useState<'全部' | '有' | '无'>('全部');
  const [adminSearchTerm, setAdminSearchTerm] = useState('');
  const [monthPlansMonth, setMonthPlansMonth] = useState('');
  const [monthPlans, setMonthPlans] = useState<Record<string, { targetFrequency: number; reason: string }>>({});
  const [showMonthPlanModal, setShowMonthPlanModal] = useState(false);
  const [monthPlanStore, setMonthPlanStore] = useState<Store | null>(null);
  const [monthPlanTarget, setMonthPlanTarget] = useState(1);
  const [monthPlanReason, setMonthPlanReason] = useState('');
  const [showExtraModal, setShowExtraModal] = useState(false);
  const [extraDate, setExtraDate] = useState('');
  const [extraStoreId, setExtraStoreId] = useState('');
  const [extraSearchTerm, setExtraSearchTerm] = useState('');
  const [extraTitle, setExtraTitle] = useState('');
  const [extraCountTowardsTarget, setExtraCountTowardsTarget] = useState(false);

  // --- 辅助函数 ---
  const getDaysInMonth = (year: number, month: number) => new Date(year, month + 1, 0).getDate();
  const getFirstDayOfMonth = (year: number, month: number) => new Date(year, month, 1).getDay();
  const formatDate = (date: Date) => date.toISOString().split('T')[0];
  const formatDateStr = (year: number, month: number, day: number) => {
    return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  };
  const formatMonthKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;

  const getStartOfWeek = (date: Date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day; 
    return new Date(d.setDate(diff));
  };

  const isSameDay = (d1: Date, d2: Date) => {
    return d1.getFullYear() === d2.getFullYear() &&
           d1.getMonth() === d2.getMonth() &&
           d1.getDate() === d2.getDate();
  };

  // --- Toast ---
  const showToast = useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3000);
  }, []);

  useEffect(() => {
    const flag = sessionStorage.getItem('auth_session_expired');
    if (!flag) return;
    sessionStorage.removeItem('auth_session_expired');
    showToast('登录已过期，请重新登录', 'info');
  }, [showToast]);

  // --- Auth 逻辑 ---
  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(authFormData)
      });
      const data = await res.json();
      if (res.ok) {
        const authUser = { ...data.user, token: data.token };
        setUser(authUser);
        setCurrentUser(authUser.name);
        localStorage.setItem('auth_user', JSON.stringify(authUser));
        showToast('登录成功', 'success');
      } else {
        showToast(data.error || '手机号或密码错误', 'error');
      }
    } catch (err) {
      showToast('网络错误', 'error');
    }
  };

  const handleLogout = () => {
    setUser(null);
    setCurrentUser('');
    localStorage.removeItem('auth_user');
    showToast('已退出登录', 'info');
  };

  const handleSessionExpired = useCallback(() => {
    setUser(null);
    setCurrentUser('');
    localStorage.removeItem('auth_user');
    showToast('登录已过期，请重新登录', 'info');
  }, [showToast]);

  // --- API ---
  const authenticatedFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${user?.token}`
    };
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
      handleSessionExpired();
      throw new Error('Session expired');
    }
    if (res.status === 403) {
      throw new Error('Permission denied');
    }
    return res;
  }, [user, handleSessionExpired]);

  // --- 管理员账号管理逻辑 ---
  const fetchManagedUsers = useCallback(async () => {
    if (user?.role !== 'admin') return;
    try {
      const res = await authenticatedFetch(`${API_BASE}/admin/users`);
      if (res.ok) {
        const data = await res.json();
        setManagedUsers(data);
      }
    } catch (err) { console.error(err); }
  }, [user, authenticatedFetch]);

  const handleSaveManagedUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    
    // 校验逻辑
    if (editingUser.name && (editingUser.name.length < 2 || editingUser.name.length > 20)) {
      return showToast('姓名需在2-20字符之间', 'error');
    }
    if (editingUser.phone && !/^1[3-9]\d{9}$/.test(editingUser.phone)) {
      return showToast('手机号格式错误', 'error');
    }
    if (editingUser.password && !/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/.test(editingUser.password)) {
      return showToast('密码需8位以上，包含大小写字母和数字', 'error');
    }

    const isNew = !editingUser.id;
    const url = isNew ? `${API_BASE}/admin/users` : `${API_BASE}/admin/users/${editingUser.id}`;
    const method = isNew ? 'POST' : 'PUT';

    try {
      const res = await authenticatedFetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingUser)
      });
      if (res.ok) {
        showToast(isNew ? '创建成功' : '更新成功', 'success');
        setShowUserModal(false);
        setEditingUser(null);
        fetchManagedUsers();
      } else {
        const data = await res.json();
        showToast(data.error || '保存失败', 'error');
      }
    } catch (err) { showToast('保存出错', 'error'); }
  };

  const fetchAllData = useCallback(async (silent = false) => {
    if (!user) return;
    try {
      if (!silent) setIsLoading(true);
      const [resStores, resExperts, resVisits] = await Promise.all([
        authenticatedFetch(`${API_BASE}/stores`),
        authenticatedFetch(`${API_BASE}/experts`),
        authenticatedFetch(`${API_BASE}/visits`) 
      ]);

      const dataStores = await resStores.json();
      const dataExperts = await resExperts.json();
      const dataVisits = await resVisits.json();

      setStores(dataStores);
      setExperts(dataExperts);
      setVisits(dataVisits);

      const preferredUser = user?.name;
      const hasPreferred = Boolean(preferredUser && dataExperts.includes(preferredUser));
      const isCurrentValid = Boolean(currentUser && dataExperts.includes(currentUser));
      if (!isCurrentValid && dataExperts.length > 0) {
        setCurrentUser(hasPreferred ? (preferredUser as string) : dataExperts[0]);
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
      if (!silent) showToast("数据加载失败", 'error');
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [user, currentUser, showToast, authenticatedFetch]);

  const fetchMonthPlans = useCallback(async (month: string) => {
    if (!user) return;
    try {
      const res = await authenticatedFetch(`${API_BASE}/store-month-plans?month=${encodeURIComponent(month)}`);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || '加载月度计划失败');
      }
      const rows = await res.json();
      const map: Record<string, { targetFrequency: number; reason: string }> = {};
      for (const r of rows || []) {
        if (!r?.storeId) continue;
        map[String(r.storeId)] = { targetFrequency: Number(r.targetFrequency) || 0, reason: String(r.reason || '') };
      }
      setMonthPlans(map);
    } catch (e) {
      console.error(e);
      showToast(`月度计划加载失败：${e instanceof Error ? e.message : String(e)}`, 'error');
      setMonthPlans({});
    }
  }, [user, authenticatedFetch, showToast]);

  useEffect(() => {
    if (user) {
      fetchAllData();
      if (user.role === 'admin') fetchManagedUsers();
    }
  }, [user, fetchAllData, fetchManagedUsers]);

  useEffect(() => {
    if (!user) return;
    const month = formatMonthKey(currentDate);
    if (month === monthPlansMonth) return;
    setMonthPlansMonth(month);
    fetchMonthPlans(month);
  }, [user, currentDate, fetchMonthPlans, monthPlansMonth]);

  useEffect(() => {
    dragHoverDateRef.current = dragHoverDate;
  }, [dragHoverDate]);

  useEffect(() => {
    touchDragRef.current = touchDrag;
  }, [touchDrag]);

  useEffect(() => {
    return () => {
      if (dropFlashTimerRef.current) window.clearTimeout(dropFlashTimerRef.current);
      if (touchLongPressTimerRef.current) window.clearTimeout(touchLongPressTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!touchDrag) return;
    let lastMoveTs = 0;
    const onMove = (ev: TouchEvent) => {
      if (!touchDragRef.current) return;
      if (ev.touches.length !== 1) return;
      const now = Date.now();
      if (now - lastMoveTs < 16) return;
      lastMoveTs = now;
      ev.preventDefault();
      const t = ev.touches[0];
      setTouchDrag(prev => prev ? ({ ...prev, x: t.clientX, y: t.clientY }) : prev);
      const el = document.elementFromPoint(t.clientX, t.clientY) as any;
      const dropEl = el?.closest?.('[data-drop-date]') as HTMLElement | null;
      const date = dropEl?.getAttribute('data-drop-date') || null;
      if (date) setDragHoverDate(date);
    };
    const onEnd = () => {
      const cur = touchDragRef.current;
      const targetDate = dragHoverDateRef.current;
      setTouchDrag(null);
      setDragging(null);
      setDragHoverDate(null);
      touchStartPointRef.current = null;
      if (cur) lastTouchDragEndRef.current = Date.now();
      if (cur && targetDate && targetDate !== cur.originDate) {
        updateVisitDate(cur.visitId, targetDate);
      }
    };
    window.addEventListener('touchmove', onMove, { passive: false });
    window.addEventListener('touchend', onEnd);
    window.addEventListener('touchcancel', onEnd);
    return () => {
      window.removeEventListener('touchmove', onMove as any);
      window.removeEventListener('touchend', onEnd);
      window.removeEventListener('touchcancel', onEnd);
    };
  }, [touchDrag]);

  // --- 逻辑 ---

  const handleDayClick = (dateStr: string) => {
    if (Date.now() - lastTouchDragEndRef.current < 500) return;
    setSelectedDateForVisit(dateStr);
    setShowDetailsModal(true); 
  };

  const handlePrev = () => {
    if (viewMode === 'month') {
      setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
    } else {
      const newDate = new Date(currentDate);
      newDate.setDate(currentDate.getDate() - 7);
      setCurrentDate(newDate);
    }
  };

  const handleNext = () => {
    if (viewMode === 'month') {
      setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
    } else {
      const newDate = new Date(currentDate);
      newDate.setDate(currentDate.getDate() + 7);
      setCurrentDate(newDate);
    }
  };

  // 专家管理逻辑已移除，由账号管理统一接管

  // [修改] 仅显示未导入的门店用于排班
  const schedulableStores = useMemo(() => {
    return stores.filter(s => s.importStatus !== '是' && !s.deletedAt);
  }, [stores]);

  const myStores = useMemo(() => {
    // 强制过滤当前专家，不再支持“全部”
    if (!currentUser) return [];
    return schedulableStores.filter(s => s.assignedExpert === currentUser);
  }, [schedulableStores, currentUser]);

  const currentMonthVisits = useMemo(() => {
    return visits.filter(v => v.expertName === currentUser);
  }, [visits, currentUser]);

  const visitsForSelectedDate = useMemo(() => {
    if (!selectedDateForVisit) return [];
    return visits.filter(v => v.date === selectedDateForVisit && v.expertName === currentUser);
  }, [visits, selectedDateForVisit, currentUser]);

  const unscheduledStores = useMemo(() => {
    const viewMonthKey = formatMonthKey(currentDate);
    const nowMonthKey = formatMonthKey(new Date());
    if (viewMonthKey < nowMonthKey) return [];

    const prefix = `${viewMonthKey}`;
    const thisMonthVisits = visits.filter(v => v.date.startsWith(prefix) && v.expertName === currentUser && v.countTowardsTarget !== false);

    return myStores.map(store => {
      const plannedCount = thisMonthVisits.filter(v => v.storeId === store.id).length;
      if (store.serviceStartMonth && viewMonthKey < store.serviceStartMonth) return { ...store, remaining: 0, plannedCount, targetFrequency: 0 };
      if (store.serviceResumeMonth && viewMonthKey < store.serviceResumeMonth) return { ...store, remaining: 0, plannedCount, targetFrequency: 0 };

      const targetFrequency = monthPlans[store.id]?.targetFrequency ?? store.monthlyFrequency;
      const remaining = Math.max(0, targetFrequency - plannedCount);
      return { ...store, remaining, plannedCount, targetFrequency };
    }).filter(s => s.remaining > 0);
  }, [myStores, visits, currentDate, currentUser, monthPlans]);

  const isPastMonthView = useMemo(() => {
    return formatMonthKey(currentDate) < formatMonthKey(new Date());
  }, [currentDate]);

  // 辅助函数：根据条件筛选门店
  const getFilteredStores = (
    baseStores: Store[], 
    filters: { 
      importStatus: string, 
      specialRequirements: '全部' | '有' | '无',
      province: string[],
      city: string[], 
      brand: string[], 
      expert: string[] 
    }
  ) => {
    return baseStores.filter(store => {
      const matchImportStatus = 
        filters.importStatus === '全部' || 
        (filters.importStatus === '是' ? store.importStatus === '是' : store.importStatus !== '是');

      const hasSpecialRequirements = Boolean(store.specialRequirements && store.specialRequirements.trim() !== '');
      const matchSpecialRequirements =
        filters.specialRequirements === '全部' ||
        (filters.specialRequirements === '有' ? hasSpecialRequirements : !hasSpecialRequirements);
      
      const matchProvince = filters.province.includes('全部') || filters.province.includes(store.province);
      const matchCity = filters.city.includes('全部') || filters.city.includes(store.city);
      const matchBrand = filters.brand.includes('全部') || filters.brand.includes(store.brand);
      
      let matchExpert = true;
      if (filters.expert.includes('全部')) {
        matchExpert = true;
      } else {
        const hasUnassigned = filters.expert.includes('待分配');
        const hasSpecific = filters.expert.some(e => e !== '待分配' && e !== '全部');
        
        if (hasUnassigned && !store.assignedExpert) matchExpert = true;
        else if (hasSpecific && filters.expert.includes(store.assignedExpert)) matchExpert = true;
        else matchExpert = false;
      }
      
      return matchImportStatus && matchSpecialRequirements && matchProvince && matchCity && matchBrand && matchExpert;
    });
  };

  // [修改] 实现筛选属性的拼音排序和级联联动
  const uniqueProvinces = useMemo(() => {
    const filtered = getFilteredStores(stores, {
      importStatus: adminFilterImportStatus,
      specialRequirements: adminFilterSpecialRequirements,
      province: ['全部'],
      city: adminFilterCity,
      brand: adminFilterBrand,
      expert: adminFilterExpert
    });
    const provinces = Array.from(new Set(filtered.map(s => s.province))).filter(p => typeof p === 'string' && p.trim() !== '');
    return ['全部', ...provinces.sort((a, b) => a.localeCompare(b, 'zh-CN'))];
  }, [stores, adminFilterImportStatus, adminFilterSpecialRequirements, adminFilterCity, adminFilterBrand, adminFilterExpert]);

  const uniqueCities = useMemo(() => {
    const filtered = getFilteredStores(stores, {
      importStatus: adminFilterImportStatus,
      specialRequirements: adminFilterSpecialRequirements,
      province: adminFilterProvince,
      city: ['全部'],
      brand: adminFilterBrand,
      expert: adminFilterExpert
    });
    const cities = Array.from(new Set(filtered.map(s => s.city))).filter(c => typeof c === 'string' && c.trim() !== '');
    return ['全部', ...cities.sort((a, b) => a.localeCompare(b, 'zh-CN'))];
  }, [stores, adminFilterImportStatus, adminFilterSpecialRequirements, adminFilterProvince, adminFilterBrand, adminFilterExpert]);

  const uniqueBrands = useMemo(() => {
    const filtered = getFilteredStores(stores, {
      importStatus: adminFilterImportStatus,
      specialRequirements: adminFilterSpecialRequirements,
      province: adminFilterProvince,
      city: adminFilterCity,
      brand: ['全部'],
      expert: adminFilterExpert
    });
    const brands = Array.from(new Set(filtered.map(s => s.brand))).filter(b => typeof b === 'string' && b.trim() !== '');
    return ['全部', ...brands.sort((a, b) => a.localeCompare(b, 'zh-CN'))];
  }, [stores, adminFilterImportStatus, adminFilterSpecialRequirements, adminFilterProvince, adminFilterCity, adminFilterExpert]);

  const sortedExperts = useMemo(() => {
    // 过滤非字符串数据，防止 localeCompare 报错
    return experts.filter(e => typeof e === 'string').sort((a, b) => a.localeCompare(b, 'zh-CN'));
  }, [experts]);

  const filterOptionsExperts = useMemo(() => {
    const filtered = getFilteredStores(stores, {
      importStatus: adminFilterImportStatus,
      specialRequirements: adminFilterSpecialRequirements,
      province: adminFilterProvince,
      city: adminFilterCity,
      brand: adminFilterBrand,
      expert: ['全部']
    });
    
    // 提取所有涉及的专家
    const expertsInView = new Set<string>();
    filtered.forEach(s => {
      if (s.assignedExpert) expertsInView.add(s.assignedExpert);
    });
    
    // 过滤 sortedExperts (所有专家列表) 中存在于当前视图的专家
    // 另外，如果 filtered 中包含未分配的门店，是否要显示“待分配”？通常是的。
    const hasUnassigned = filtered.some(s => !s.assignedExpert);
    
    const validExperts = sortedExperts.filter(e => expertsInView.has(e));
    
    const options = ['全部'];
    if (hasUnassigned) options.push('待分配');
    return [...options, ...validExperts];
  }, [stores, adminFilterImportStatus, adminFilterSpecialRequirements, adminFilterProvince, adminFilterCity, adminFilterBrand, sortedExperts]);

  // [修改] 当联动筛选导致当前选中项无效时，自动重置
  useEffect(() => {
    if (!adminFilterProvince.includes('全部')) {
      const isValid = adminFilterProvince.every(p => uniqueProvinces.includes(p));
      if (!isValid) setAdminFilterProvince(['全部']);
    }
    // 重置城市
    if (!adminFilterCity.includes('全部')) {
      const isValid = adminFilterCity.every(c => uniqueCities.includes(c));
      if (!isValid) setAdminFilterCity(['全部']);
    }
    // 重置品牌
    if (!adminFilterBrand.includes('全部')) {
      const isValid = adminFilterBrand.every(b => uniqueBrands.includes(b));
      if (!isValid) setAdminFilterBrand(['全部']);
    }
    // 重置专家
    if (!adminFilterExpert.includes('全部')) {
      // filterOptionsExperts 包含 '全部', '待分配', 和专家名
      const isValid = adminFilterExpert.every(e => filterOptionsExperts.includes(e));
      if (!isValid) setAdminFilterExpert(['全部']);
    }
  }, [uniqueProvinces, uniqueCities, uniqueBrands, filterOptionsExperts, adminFilterProvince, adminFilterCity, adminFilterBrand, adminFilterExpert]);

  const filteredStores = useMemo(() => {
    return getFilteredStores(stores, {
      importStatus: adminFilterImportStatus,
      specialRequirements: adminFilterSpecialRequirements,
      province: adminFilterProvince,
      city: adminFilterCity,
      brand: adminFilterBrand,
      expert: adminFilterExpert
    }).filter(store => {
      const searchLower = adminSearchTerm.toLowerCase();
      const matchSearch = store.name.toLowerCase().includes(searchLower) || store.id.toLowerCase().includes(searchLower);
      return matchSearch;
    });
  }, [stores, adminFilterProvince, adminFilterCity, adminFilterBrand, adminFilterExpert, adminFilterImportStatus, adminFilterSpecialRequirements, adminSearchTerm]);

  // 批量/单选 门店
  const toggleStoreSelection = (storeId: string) => {
    setSelectedStoreIds(prev => 
      prev.includes(storeId) ? prev.filter(id => id !== storeId) : [...prev, storeId]
    );
  };

  const handleBatchAddVisits = async () => {
    if (selectedStoreIds.length === 0) return;
    const dateToAdd = selectedDateForVisit || formatDate(new Date()); 

    const newVisits: Visit[] = [];
    const promises = selectedStoreIds.map(storeId => {
      const newVisit: Visit = {
        id: crypto.randomUUID(),
        storeId,
        date: dateToAdd,
        expertName: currentUser || '未分配',
        status: 'planned'
      };
      newVisits.push(newVisit);
      return authenticatedFetch(`${API_BASE}/visits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newVisit)
      });
    });

    try {
      await Promise.all(promises);
      setVisits(prev => [...prev, ...newVisits]); 
      showToast(`成功添加 ${newVisits.length} 个门店到 ${dateToAdd}`, 'success');
      setSelectedStoreIds([]); 
      setShowAddModal(false); 
    } catch (e) {
      console.error(e);
      showToast('部分任务添加失败，请刷新重试', 'error');
    }
  };

  const handleRemoveVisit = async (visitId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const res = await authenticatedFetch(`${API_BASE}/visits/${visitId}`, { method: 'DELETE' });
      if (res.ok) {
        setVisits(visits.filter(v => v.id !== visitId));
        showToast('排班已取消', 'info');
      }
    } catch (e) { console.error(e); }
  };

  const flashDrop = (dateStr: string) => {
    setDropFlashDate(dateStr);
    if (dropFlashTimerRef.current) window.clearTimeout(dropFlashTimerRef.current);
    dropFlashTimerRef.current = window.setTimeout(() => setDropFlashDate(null), 450);
  };

  const hasScheduleConflict = (storeId: string, dateStr: string, ignoreVisitId?: string) => {
    return visits.some(v => v.storeId === storeId && v.date === dateStr && v.expertName === currentUser && v.id !== ignoreVisitId);
  };

  const createVisitForStoreOnDate = async (storeId: string, dateStr: string) => {
    if (!currentUser) return;
    if (hasScheduleConflict(storeId, dateStr)) {
      showToast('该日期已安排过该门店', 'error');
      return;
    }
    const newVisit: Visit = {
      id: crypto.randomUUID(),
      storeId,
      date: dateStr,
      expertName: currentUser,
      status: 'planned'
    };
    setVisits(prev => [...prev, newVisit]);
    try {
      const res = await authenticatedFetch(`${API_BASE}/visits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newVisit)
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'API Error');
      }
      flashDrop(dateStr);
      showToast('已添加排班', 'success');
    } catch (err: any) {
      setVisits(prev => prev.filter(v => v.id !== newVisit.id));
      showToast(`拖拽失败：${err.message || '网络错误'}`, 'error');
    }
  };

  const updateVisitDate = async (visitId: string, targetDate: string) => {
    const existing = visits.find(v => v.id === visitId);
    if (!existing) return;
    if (existing.date === targetDate) return;
    if (hasScheduleConflict(existing.storeId, targetDate, visitId)) {
      showToast('目标日期已存在相同门店安排', 'error');
      return;
    }
    setVisits(prev => prev.map(v => v.id === visitId ? { ...v, date: targetDate } : v));
    try {
      const res = await authenticatedFetch(`${API_BASE}/visits/${visitId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: targetDate })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'API Error');
      }
      flashDrop(targetDate);
      showToast('已更新日期', 'success');
    } catch (err: any) {
      setVisits(prev => prev.map(v => v.id === visitId ? existing : v));
      showToast(`拖拽失败：${err.message || '网络错误'}`, 'error');
    }
  };

  const handleDragEnd = () => {
    setDragging(null);
    setDragHoverDate(null);
  };

  const beginStoreDrag = (storeId: string) => (e: React.DragEvent) => {
    setDragging({ kind: 'store', id: storeId });
    e.dataTransfer.effectAllowed = 'move';
    const payload = JSON.stringify({ kind: 'store', id: storeId });
    e.dataTransfer.setData('application/json', payload);
    e.dataTransfer.setData('text/plain', payload);
  };

  const beginVisitDrag = (visitId: string) => (e: React.DragEvent) => {
    setDragging({ kind: 'visit', id: visitId });
    e.dataTransfer.effectAllowed = 'move';
    const payload = JSON.stringify({ kind: 'visit', id: visitId });
    e.dataTransfer.setData('application/json', payload);
    e.dataTransfer.setData('text/plain', payload);
  };

  const handleCalendarDragOver = (dateStr: string) => (e: React.DragEvent) => {
    if (!dragging) return;
    e.preventDefault();
    const now = Date.now();
    if (now - dragOverLastTsRef.current < 60) return;
    dragOverLastTsRef.current = now;
    setDragHoverDate(dateStr);
  };

  const handleCalendarDragLeave = (dateStr: string) => () => {
    if (dragHoverDateRef.current === dateStr) setDragHoverDate(null);
  };

  const handleCalendarDrop = (dateStr: string) => async (e: React.DragEvent) => {
    if (!dragging) return;
    e.preventDefault();
    e.stopPropagation();
    setDragHoverDate(null);
    const raw = e.dataTransfer.getData('application/json') || e.dataTransfer.getData('text/plain') || '';
    try {
      const parsed = JSON.parse(raw);
      if (parsed?.kind === 'store') {
        await createVisitForStoreOnDate(parsed.id, dateStr);
      } else if (parsed?.kind === 'visit') {
        await updateVisitDate(parsed.id, dateStr);
      }
    } catch (err) {
      showToast('拖拽数据解析失败', 'error');
    } finally {
      handleDragEnd();
    }
  };

  const beginMobileVisitLongPress = (visitId: string, label: string, originDate: string) => (e: React.TouchEvent) => {
    if (viewMode !== 'week') return;
    if (e.touches.length !== 1) return;
    const t = e.touches[0];
    touchStartPointRef.current = { x: t.clientX, y: t.clientY };
    if (touchLongPressTimerRef.current) window.clearTimeout(touchLongPressTimerRef.current);
    touchLongPressTimerRef.current = window.setTimeout(() => {
      const start = touchStartPointRef.current;
      if (!start) return;
      setDragging({ kind: 'visit', id: visitId });
      setTouchDrag({ visitId, label, x: start.x, y: start.y, originDate });
      setDragHoverDate(originDate);
    }, 320);
  };

  const cancelMobileLongPress = (e: React.TouchEvent) => {
    if (touchLongPressTimerRef.current) {
      const start = touchStartPointRef.current;
      const t = e.touches[0];
      if (start && t) {
        const dx = t.clientX - start.x;
        const dy = t.clientY - start.y;
        if (Math.hypot(dx, dy) > 10) {
          window.clearTimeout(touchLongPressTimerRef.current);
          touchLongPressTimerRef.current = null;
        }
      }
    }
  };

  const cancelMobileLongPressEnd = () => {
    if (touchLongPressTimerRef.current) window.clearTimeout(touchLongPressTimerRef.current);
    touchLongPressTimerRef.current = null;
  };

  const handleImport = async () => {
    try {
      const lines = csvText.trim().split('\n');
      if (lines.length < 1) throw new Error('数据为空');
      const newStores: Store[] = [];
      const startIdx = (lines[0].toLowerCase().includes('id') || lines[0].toLowerCase().includes('名称') || lines[0].toLowerCase().includes('门店')) ? 1 : 0;
      for (let i = startIdx; i < lines.length; i++) {
        let line = lines[i].trim();
        if (!line) continue;
        
        // 增强的分隔符逻辑：支持制表符 \t, 逗号, 以及连续 2 个以上的空格（常见于从某些表格直接粘贴）
        let cols = line.split(/[,\t]|\s{2,}/);
        cols = cols.map(c => c.trim().replace(/^"|"$/g, ''));
        
        // 如果上面没切开，尝试单空格（但容易误切带空格的店名，所以作为兜底）
        if (cols.length < 4) {
          cols = line.split(/\s+/);
          cols = cols.map(c => c.trim().replace(/^"|"$/g, ''));
        }

        if (cols.length < 4) {
          console.warn(`跳过列数不足的行 ${i + 1}:`, line);
          continue;
        } 
        
        const id = cols[0];
        const name = cols[1];
        const brand = cols[2];
        let province = '';
        let city = '';
        let assignedExpert = '';
        let frequencyIdx = 0;
        let requirementsIdx = 0;
        let importStatusIdx = 0;
        
        if (cols.length >= 9) {
          province = cols[3] || '';
          city = cols[4] || '';
          assignedExpert = cols[5] || '';
          frequencyIdx = 6;
          requirementsIdx = 7;
          importStatusIdx = 8;
        } else {
          city = cols[3] || '';
          assignedExpert = cols[4] || '';
          frequencyIdx = 5;
          requirementsIdx = 6;
          importStatusIdx = 7;
        }
        
        if (!id || !name || !city) {
          console.warn(`跳过无效行 ${i + 1}: ID, 名称, 城市 不能为空`, cols);
          continue;
        }

        let frequency = 1;
        if (cols[frequencyIdx]) {
          const parsed = parseInt(cols[frequencyIdx]);
          if (!isNaN(parsed) && parsed > 0) frequency = parsed;
        }
        
        const specialRequirements = cols[requirementsIdx] || '';
        const importStatus = cols[importStatusIdx] || '';

        newStores.push({
          id, name, brand, province, city,
          assignedExpert, specialRequirements, monthlyFrequency: frequency,
          importStatus
        });
      }
      const res = await authenticatedFetch(`${API_BASE}/stores/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newStores)
      });
      if (res.ok) {
        setCsvText(''); fetchAllData(true); 
        showToast(`成功导入 ${newStores.length} 条门店数据`, 'success');
      } else { 
        const errorData = await res.json();
        throw new Error(errorData.error || 'API Error'); 
      }
    } catch (e: any) { 
      showToast(`导入失败: ${e.message}`, 'error'); 
    }
  };

  const handleExport = () => {
    let csvContent = "\ufeff门店ID,门店名称,品牌,省份,城市,负责专家,服务频次,特殊需求,导入状态\n";
    stores.forEach(store => {
      const row = [
        store.id, 
        store.name, 
        store.brand || '', 
        store.province || '',
        store.city || '', 
        store.assignedExpert || '', 
        store.monthlyFrequency, 
        store.specialRequirements || '',
        store.importStatus || ''
      ].map(field => `"${field}"`).join(",");
      csvContent += row + "\n";
    });
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `store_data.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('导出开始', 'success');
  };

  const handleArchiveStore = async (id: string) => {
    if(!confirm('确定停用门店？停用后门店将不再参与排班，但历史记录会保留。')) return;
    try {
      const res = await authenticatedFetch(`${API_BASE}/stores/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setStores(stores.map(s => s.id === id ? { ...s, deletedAt: new Date().toISOString() } : s));
        showToast('已停用', 'info');
      } else {
        const data = await res.json();
        showToast(data.error || '停用失败', 'error');
      }
    } catch (e) {
      showToast(`停用出错：${e instanceof Error ? e.message : String(e)}`, 'error');
    }
  };

  const handleRestoreStore = async (id: string) => {
    if(!confirm('确定恢复门店？恢复后将重新参与排班。')) return;
    try {
      const res = await authenticatedFetch(`${API_BASE}/stores/${id}/restore`, { method: 'POST' });
      if (res.ok) {
        const resumeMonth = formatMonthKey(new Date());
        setStores(stores.map(s => s.id === id ? { ...s, deletedAt: null, serviceResumeMonth: resumeMonth } : s));
        showToast('已恢复', 'success');
      } else {
        const data = await res.json();
        showToast(data.error || '恢复失败', 'error');
      }
    } catch (e) {
      showToast(`恢复出错：${e instanceof Error ? e.message : String(e)}`, 'error');
    }
  };

  const openMonthPlanModalForStore = (store: Store) => {
    const month = formatMonthKey(currentDate);
    const plan = monthPlans[store.id];
    setMonthPlanStore(store);
    setMonthPlanTarget(plan?.targetFrequency ?? store.monthlyFrequency);
    setMonthPlanReason(plan?.reason ?? '');
    setShowMonthPlanModal(true);
    if (month !== monthPlansMonth) setMonthPlansMonth(month);
  };

  const handleSaveMonthPlan = async () => {
    if (!monthPlanStore) return;
    const month = formatMonthKey(currentDate);
    const target = Math.max(0, Math.trunc(Number(monthPlanTarget) || 0));
    try {
      const res = await authenticatedFetch(`${API_BASE}/stores/${monthPlanStore.id}/month-plan`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, targetFrequency: target, reason: monthPlanReason })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || '保存失败');
      }
      setMonthPlans(prev => ({ ...prev, [monthPlanStore.id]: { targetFrequency: target, reason: monthPlanReason } }));
      setShowMonthPlanModal(false);
      setMonthPlanStore(null);
      showToast('本月计划已更新', 'success');
    } catch (e) {
      showToast(`保存失败：${e instanceof Error ? e.message : String(e)}`, 'error');
    }
  };

  const handleClearMonthPlan = async () => {
    if (!monthPlanStore) return;
    const month = formatMonthKey(currentDate);
    try {
      const res = await authenticatedFetch(`${API_BASE}/stores/${monthPlanStore.id}/month-plan?month=${encodeURIComponent(month)}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || '清除失败');
      }
      setMonthPlans(prev => {
        const next = { ...prev };
        delete next[monthPlanStore.id];
        return next;
      });
      setShowMonthPlanModal(false);
      setMonthPlanStore(null);
      showToast('已清除本月覆盖', 'success');
    } catch (e) {
      showToast(`清除失败：${e instanceof Error ? e.message : String(e)}`, 'error');
    }
  };

  const openExtraVisitModal = (dateStr?: string) => {
    const resolvedDate = dateStr || selectedDateForVisit || formatDate(new Date());
    setExtraDate(resolvedDate);
    setExtraStoreId('');
    setExtraSearchTerm('');
    setExtraTitle('');
    setExtraCountTowardsTarget(false);
    setShowExtraModal(true);
  };

  const handleCreateExtraVisit = async () => {
    const expertName = currentUser || user?.name || '';
    if (!expertName) return showToast('未选择专家', 'error');
    if (!extraDate) return showToast('请选择日期', 'error');
    if (!extraStoreId) return showToast('请选择门店', 'error');
    if (!extraTitle.trim()) return showToast('请填写上门原因', 'error');

    const newVisit: Visit = {
      id: crypto.randomUUID(),
      storeId: extraStoreId,
      date: extraDate,
      expertName,
      status: 'planned',
      type: 'extra',
      title: extraTitle,
      countTowardsTarget: user?.role === 'admin' ? extraCountTowardsTarget : false
    };
    try {
      const res = await authenticatedFetch(`${API_BASE}/visits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newVisit)
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || '创建失败');
      }
      setVisits(prev => [...prev, newVisit]);
      setShowExtraModal(false);
      showToast('已创建临时上门', 'success');
    } catch (e) {
      showToast(`创建失败：${e instanceof Error ? e.message : String(e)}`, 'error');
    }
  };

  const handleSaveEdit = async () => {
    if (!editingStore) return;
    try {
      const res = await authenticatedFetch(`${API_BASE}/stores/${editingStore.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingStore)
      });
      if (res.ok) {
        setStores(stores.map(s => s.id === editingStore.id ? editingStore : s));
        setEditingStore(null);
        showToast('已保存', 'success');
      } else {
        const data = await res.json();
        showToast(data.error || '保存失败', 'error');
      }
    } catch (e) { console.error(e); showToast('保存出错', 'error'); }
  };

  // --- 视图渲染 ---

  const renderMonthView = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);
    const days = [];
    
    const weekHeader = (
      <div className="grid grid-cols-7 border-b border-gray-200 bg-gray-50">
        {['日', '一', '二', '三', '四', '五', '六'].map(d => <div key={d} className="py-2 text-center text-xs font-medium text-gray-500">{d}</div>)}
      </div>
    );
    
    for (let i = 0; i < firstDay; i++) days.push(<div key={`empty-${i}`} className="h-24 bg-gray-50/50 border-r border-b border-gray-100"></div>);

    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = formatDateStr(year, month, d);
      const isToday = dateStr === formatDate(new Date());
      const dayVisits = currentMonthVisits.filter(v => v.date === dateStr);
      const hasVisits = dayVisits.length > 0;
      const isSelected = selectedDateForVisit === dateStr;
      const isDragHover = dragHoverDate === dateStr;
      const isFlash = dropFlashDate === dateStr;

      days.push(
        <div 
          key={dateStr} 
          onClick={() => handleDayClick(dateStr)} 
          onDragOver={handleCalendarDragOver(dateStr)}
          onDrop={handleCalendarDrop(dateStr)}
          onDragLeave={handleCalendarDragLeave(dateStr)}
          className={`min-h-[6rem] p-1 border-r border-b border-gray-200 relative cursor-pointer transition-colors 
            ${isSelected ? 'bg-blue-100 ring-2 ring-inset ring-blue-400' : isToday ? 'bg-blue-50/30' : 'bg-white hover:bg-gray-50'}
            ${isDragHover ? 'ring-2 ring-blue-400 bg-blue-50' : ''}
            ${isFlash ? 'animate-pulse bg-green-50 ring-2 ring-green-300' : ''}
          `}
        >
          <div className="flex justify-between items-start">
            <span className={`text-sm font-medium w-6 h-6 flex items-center justify-center rounded-full ${isToday ? 'bg-blue-600 text-white' : 'text-gray-700'}`}>{d}</span>
            {hasVisits && (<span className="hidden md:inline-block text-xs bg-green-100 text-green-800 px-1 rounded scale-90 origin-top-right">{dayVisits.length} 次</span>)}
          </div>
          <div className="hidden md:block mt-1 space-y-1 overflow-y-auto max-h-[4.5rem] no-scrollbar">
            {dayVisits.slice(0, 3).map(visit => {
              const store = stores.find(s => s.id === visit.storeId);
              const todayStr = formatDate(new Date());
              const isAutoCompleted = visit.status === 'completed' && visit.date < todayStr;
              const canDrag = !store?.deletedAt && (visit.status === 'planned' || isAutoCompleted);
              const isExtra = visit.type === 'extra';
              const pillClass = !canDrag
                ? 'bg-gray-100 text-gray-500 cursor-not-allowed opacity-80'
                : isExtra
                  ? 'bg-orange-100 text-orange-900 cursor-grab active:cursor-grabbing'
                  : 'bg-blue-100 text-blue-900 cursor-grab active:cursor-grabbing';
              return (
                // [修改] 加入原生 tooltip，允许换行显示避免文字被阶段
                <div
                  key={visit.id}
                  draggable={canDrag}
                  onDragStart={canDrag ? beginVisitDrag(visit.id) : undefined}
                  onDragEnd={handleDragEnd}
                  title={`${store?.name} (${store?.brand} · ${store?.city})`}
                  className={`whitespace-normal break-words line-clamp-2 leading-tight text-[10px] p-0.5 rounded px-1 mb-0.5 transition ${pillClass} ${dragging?.kind === 'visit' && dragging.id === visit.id ? 'opacity-50' : ''}`}
                >
                  {isExtra ? `临时：${store?.name}` : store?.name}
                </div>
              );
            })}
             {dayVisits.length > 3 && <div className="text-[10px] text-gray-400 text-center">+{dayVisits.length - 3} 更多</div>}
          </div>
          <div className="md:hidden mt-2 flex flex-wrap gap-1 justify-center">
            {dayVisits.slice(0, 3).map((_, idx) => (<div key={idx} className="w-1.5 h-1.5 bg-blue-400 rounded-full"></div>))}
            {dayVisits.length > 3 && <div className="w-1.5 h-1.5 bg-gray-300 rounded-full"></div>}
          </div>
        </div>
      );
    }

    return (
      <>
        {weekHeader}
        <div className="grid grid-cols-7 flex-1 auto-rows-fr bg-gray-100 gap-px border-b border-gray-200">
          {days}
        </div>
      </>
    );
  };

  const renderDesktopWeekView = () => {
    const startOfWeek = getStartOfWeek(currentDate);
    const weekDays = [];

    for (let i = 0; i < 7; i++) {
      const d = new Date(startOfWeek);
      d.setDate(startOfWeek.getDate() + i);
      const dateStr = formatDate(d);
      const isToday = isSameDay(d, new Date());
      const dayVisits = currentMonthVisits.filter(v => v.date === dateStr);
      const isSelected = selectedDateForVisit === dateStr;
      const isDragHover = dragHoverDate === dateStr;
      const isFlash = dropFlashDate === dateStr;

      weekDays.push(
        <div 
          key={dateStr} 
          onClick={() => handleDayClick(dateStr)}
          onDragOver={handleCalendarDragOver(dateStr)}
          onDrop={handleCalendarDrop(dateStr)}
          onDragLeave={handleCalendarDragLeave(dateStr)}
          className={`flex-1 flex flex-col min-w-[140px] border-r border-gray-200 
            ${isSelected ? 'bg-blue-50 ring-2 ring-inset ring-blue-300' : isToday ? 'bg-blue-50/20' : 'bg-white'}
            ${isDragHover ? 'ring-2 ring-blue-400 bg-blue-50' : ''}
            ${isFlash ? 'animate-pulse bg-green-50 ring-2 ring-green-300' : ''}
          `}
        >
          <div className={`p-3 text-center border-b border-gray-100 ${isToday ? 'bg-blue-100/50' : 'bg-gray-50'}`}>
            <div className={`text-xs font-bold ${isToday ? 'text-blue-600' : 'text-gray-500'}`}>周{['日', '一', '二', '三', '四', '五', '六'][d.getDay()]}</div>
            <div className={`text-lg font-bold ${isToday ? 'text-blue-800' : 'text-gray-800'}`}>{d.getDate()}</div>
          </div>
          
          <div className="flex-1 p-2 space-y-2 overflow-y-auto">
            <div className="h-full min-h-[100px]" title="点击选中该日期并进行排班">
              {dayVisits.map(visit => {
                const store = stores.find(s => s.id === visit.storeId);
                const todayStr = formatDate(new Date());
                const isAutoCompleted = visit.status === 'completed' && visit.date < todayStr;
                const canDrag = !store?.deletedAt && (visit.status === 'planned' || isAutoCompleted);
                const canDelete = !store?.deletedAt && visit.status === 'planned';
                const isExtra = visit.type === 'extra';
                const cardClass = !canDrag
                  ? 'bg-gray-50 border-l-4 border-l-gray-300 cursor-not-allowed opacity-80'
                  : isExtra
                    ? 'bg-orange-50 border-l-4 border-l-orange-500 hover:shadow-md cursor-grab active:cursor-grabbing'
                    : 'bg-white border-l-4 border-l-blue-500 hover:shadow-md cursor-grab active:cursor-grabbing';
                return (
                  <div
                    key={visit.id}
                    draggable={canDrag}
                    onDragStart={canDrag ? beginVisitDrag(visit.id) : undefined}
                    onDragEnd={handleDragEnd}
                    className={`relative group shadow-sm border border-gray-200 rounded p-2 transition ${cardClass} ${dragging?.kind === 'visit' && dragging.id === visit.id ? 'opacity-50' : ''}`}
                  >
                    {/* [修改] 移除 truncate，允许店名完整换行显示，并增加原生 tooltip */}
                    <div className="font-bold text-gray-800 text-sm whitespace-normal break-words leading-snug pr-4" title={`${store?.name} (${store?.brand} · ${store?.city})`}>
                      {isExtra ? `临时：${store?.name}` : store?.name}
                    </div>
                    {isExtra && <div className="text-[10px] text-orange-700 mt-1 whitespace-normal break-words leading-tight">{visit.title || ''}</div>}
                    <div className="flex items-center gap-1 text-[10px] text-gray-500 mt-1"><MapPin size={10}/> {store?.city}</div>
                    {canDelete && (
                      <button onClick={(e) => handleRemoveVisit(visit.id, e)} className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition"><X size={12}/></button>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      );
    }
    return <div className="flex h-full overflow-x-auto divide-x divide-gray-200">{weekDays}</div>;
  };

  const renderMobileWeekView = () => {
    const startOfWeek = getStartOfWeek(currentDate);
    const weekRows = [];

    for (let i = 0; i < 7; i++) {
      const d = new Date(startOfWeek);
      d.setDate(startOfWeek.getDate() + i);
      const dateStr = formatDate(d);
      const isToday = isSameDay(d, new Date());
      const dayVisits = currentMonthVisits.filter(v => v.date === dateStr);
      const isSelected = selectedDateForVisit === dateStr;
      const isDragHover = dragHoverDate === dateStr;
      const isFlash = dropFlashDate === dateStr;

      weekRows.push(
        <div
          key={dateStr}
          data-drop-date={dateStr}
          onClick={() => handleDayClick(dateStr)}
          className={`flex flex-col border-b border-gray-100 p-3 cursor-pointer ${isSelected ? 'bg-blue-50' : 'bg-white'} ${isDragHover ? 'ring-2 ring-inset ring-blue-400 bg-blue-50' : ''} ${isFlash ? 'animate-pulse bg-green-50 ring-2 ring-inset ring-green-300' : ''}`}
        >
          <div className="flex items-center gap-3 mb-2">
            <span className={`text-xl font-bold w-8 text-center ${isToday ? 'text-blue-600' : 'text-gray-900'}`}>{d.getDate()}</span>
            <div className="flex flex-col">
              <span className="text-xs text-gray-500">周{['日', '一', '二', '三', '四', '五', '六'][d.getDay()]}</span>
            </div>
            {isToday && <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 rounded self-start mt-1">今天</span>}
            <div className="flex-1"></div>
            {dayVisits.length > 0 && <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{dayVisits.length}个任务</span>}
          </div>

          <div className="pl-11 space-y-2">
            {dayVisits.length === 0 ? <div className="text-xs text-gray-300 italic">点击添加安排</div> : dayVisits.map(visit => {
                const store = stores.find(s => s.id === visit.storeId);
                const label = store?.name || '门店';
                const todayStr = formatDate(new Date());
                const isAutoCompleted = visit.status === 'completed' && visit.date < todayStr;
                const canDrag = !store?.deletedAt && (visit.status === 'planned' || isAutoCompleted);
                const canDelete = !store?.deletedAt && visit.status === 'planned';
                const isExtra = visit.type === 'extra';
                const itemClass = !canDrag
                  ? 'bg-gray-50 opacity-80'
                  : isExtra
                    ? 'bg-orange-50'
                    : 'bg-white';
                return (
                  <div
                    key={visit.id}
                    onTouchStart={canDrag ? beginMobileVisitLongPress(visit.id, label, dateStr) : undefined}
                    onTouchMove={canDrag ? cancelMobileLongPress : undefined}
                    onTouchEnd={canDrag ? cancelMobileLongPressEnd : undefined}
                    onTouchCancel={canDrag ? cancelMobileLongPressEnd : undefined}
                    className={`border border-gray-200 rounded-lg p-3 shadow-sm flex justify-between items-center transition ${itemClass} ${touchDrag?.visitId === visit.id ? 'opacity-50' : ''}`}
                  >
                    <div>
                      <div className="font-bold text-gray-800 text-sm whitespace-normal break-words leading-snug">{isExtra ? `临时：${store?.name}` : store?.name}</div>
                      {isExtra && <div className="text-[10px] text-orange-700 mt-1 whitespace-normal break-words leading-tight">{visit.title || ''}</div>}
                      <div className="text-xs text-gray-500 mt-1">{store?.brand} · {store?.city}</div>
                    </div>
                    {canDelete && <button onClick={(e) => handleRemoveVisit(visit.id, e)} className="p-2 text-gray-400 hover:text-red-500"><X size={18}/></button>}
                  </div>
                );
              })
            }
          </div>
        </div>
      );
    }
    return <div className="flex flex-col bg-white pb-6">{weekRows}</div>;
  };

  // --- 登录 视图 ---
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100 p-4">
        <div className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-md">
          <div className="flex flex-col items-center mb-8">
            <div className="bg-blue-600 p-3 rounded-2xl text-white mb-4 shadow-lg shadow-blue-200">
              <Calendar size={32} />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">ServiceMate</h1>
            <p className="text-gray-500 text-sm mt-1">管理员预置账号登录</p>
          </div>

          <form onSubmit={handleAuth} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">手机号</label>
              <input 
                type="tel" 
                required 
                placeholder="11位手机号"
                className="w-full p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
                value={authFormData.phone}
                onChange={e => setAuthFormData({...authFormData, phone: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">密码</label>
              <input 
                type="password" 
                required 
                placeholder="请输入密码"
                className="w-full p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
                value={authFormData.password}
                onChange={e => setAuthFormData({...authFormData, password: e.target.value})}
              />
            </div>
            <button 
              type="submit" 
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold hover:bg-blue-700 shadow-lg shadow-blue-200 transition transform active:scale-[0.98]"
            >
              登录
            </button>
          </form>

          <div className="mt-6 text-center text-xs text-gray-400">
            <p>未获得账号？请联系系统管理员</p>
          </div>
        </div>
        {/* Toast 集成 */}
        <div className="fixed top-4 right-4 z-[60] flex flex-col gap-2 pointer-events-none">
          {toasts.map(toast => (
            <div key={toast.id} className={`pointer-events-auto flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-in slide-in-from-right fade-in duration-300 ${toast.type === 'success' ? 'bg-green-600 text-white' : toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-gray-800 text-white'}`}>
              {toast.type === 'success' ? <CheckCircle2 size={16}/> : toast.type === 'error' ? <AlertCircle size={16}/> : <Info size={16}/>}
              {toast.message}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-50 flex-col gap-4"><Loader2 className="animate-spin text-blue-600" size={48} /><p className="text-gray-500 font-medium">正在连接...</p></div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-800 font-sans flex flex-col">
      <div className="fixed top-20 right-4 z-[60] flex flex-col gap-2 pointer-events-none">
        {toasts.map(toast => (
          <div key={toast.id} className={`pointer-events-auto flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-in slide-in-from-right fade-in duration-300 ${toast.type === 'success' ? 'bg-green-600 text-white' : toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-gray-800 text-white'}`}>
            {toast.type === 'success' ? <CheckCircle2 size={16}/> : toast.type === 'error' ? <AlertCircle size={16}/> : <Info size={16}/>}
            {toast.message}
          </div>
        ))}
      </div>
      {touchDrag && (
        <div className="fixed z-[80] pointer-events-none" style={{ left: touchDrag.x, top: touchDrag.y, transform: 'translate(-50%, -50%)' }}>
          <div className="bg-blue-600 text-white text-sm px-3 py-2 rounded-lg shadow-lg opacity-90 max-w-[70vw] whitespace-normal break-words">
            {touchDrag.label}
          </div>
        </div>
      )}

      <nav className="bg-white border-b border-gray-200 px-4 py-3 sticky top-0 z-20 shadow-sm">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2">
            <a href="/workspace" className="hidden sm:flex items-center gap-1 text-gray-500 hover:text-blue-600 transition mr-2" title="返回工作台">
              <ChevronLeft size={20} />
            </a>
            <div className="bg-blue-600 p-1.5 rounded-lg text-white"><Calendar size={20} /></div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight hidden sm:block">专家排班工具</h1>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight sm:hidden">排班助手</h1>
          </div>
          <div className="hidden md:flex items-center gap-6">
            <button onClick={() => setActiveTab('calendar')} className={`flex items-center gap-2 px-3 py-2 rounded-md transition ${activeTab === 'calendar' ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'}`}><Calendar size={18} /> 排班日历</button>
            <button onClick={() => setActiveTab('admin')} className={`flex items-center gap-2 px-3 py-2 rounded-md transition ${activeTab === 'admin' ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'}`}><Upload size={18} /> 门店库</button>
            <div className="h-6 w-px bg-gray-300"></div>
            
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 bg-gray-100 px-3 py-1.5 rounded-full">
                <Users size={16} className="text-gray-500"/>
                <select value={currentUser} onChange={(e) => setCurrentUser(e.target.value)} className="bg-transparent text-sm border-none focus:ring-0 cursor-pointer font-medium text-gray-700">
                  {/* 已移除“全部专家”选项 */}
                  {sortedExperts.map(exp => <option key={exp} value={exp}>{exp}</option>)}
                </select>
              </div>

              <div className="flex items-center gap-3 border-l pl-4">
                <div className="flex flex-col items-end">
                  <span className="text-sm font-bold text-gray-900">{user.name}</span>
                  <span className="text-[10px] bg-indigo-100 text-indigo-700 px-1.5 rounded uppercase font-bold">{user.role}</span>
                </div>
                <button 
                  onClick={handleLogout}
                  className="p-2 text-gray-400 hover:text-red-600 transition hover:bg-red-50 rounded-lg"
                  title="退出登录"
                >
                  <LogOut size={20} />
                </button>
              </div>
            </div>
          </div>
          <div className="md:hidden flex items-center gap-3">
             <div className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded-md">
              <Users size={14} className="text-gray-500"/>
              <select value={currentUser} onChange={(e) => setCurrentUser(e.target.value)} className="bg-transparent text-xs border-none focus:ring-0 w-16 truncate">
                {/* 已移除“全部”选项 */}
                {sortedExperts.map(exp => <option key={exp} value={exp}>{exp}</option>)}
              </select>
            </div>
            <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="p-2 text-gray-600">{isMobileMenuOpen ? <X size={24}/> : <Menu size={24}/>}</button>
          </div>
        </div>
        {isMobileMenuOpen && (
          <div className="md:hidden mt-3 pt-3 border-t border-gray-100 space-y-2 pb-2">
             <button onClick={() => { setActiveTab('calendar'); setIsMobileMenuOpen(false); }} className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg ${activeTab === 'calendar' ? 'bg-blue-50 text-blue-700' : 'text-gray-600'}`}><Calendar size={20} /> 排班日历</button>
            <button onClick={() => { setActiveTab('admin'); setIsMobileMenuOpen(false); }} className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg ${activeTab === 'admin' ? 'bg-blue-50 text-blue-700' : 'text-gray-600'}`}><Upload size={20} /> 门店库</button>
            <button onClick={handleLogout} className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-red-600"><LogOut size={20} /> 退出登录</button>
          </div>
        )}
      </nav>

      <main className="flex-1 max-w-7xl mx-auto w-full p-4 h-[calc(100vh-64px)] overflow-hidden flex flex-col">
        {activeTab === 'admin' && (
          <div className="space-y-6 animate-in fade-in duration-300 h-full overflow-y-auto pb-20 custom-scrollbar">
            {/* 账号管理 - 仅管理员可见 */}
            {user.role === 'admin' && (
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                  <Users className="text-blue-600" size={20}/> 账号管理
                </h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">账号将自动显示在专家列表中</span>
                  <button 
                    onClick={() => { setEditingUser({ role: 'user', status: 1 }); setShowUserModal(true); }}
                      className="flex items-center gap-1 bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm"
                    >
                      <Plus size={16}/> 新增账号
                    </button>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b">
                      <tr>
                        <th className="px-4 py-3">姓名</th>
                        <th className="px-4 py-3">手机号</th>
                        <th className="px-4 py-3">角色</th>
                        <th className="px-4 py-3">状态</th>
                        <th className="px-4 py-3 text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {managedUsers.map(u => (
                        <tr key={u.id} className="hover:bg-gray-50 transition">
                          <td className="px-4 py-3 font-medium">{u.name}</td>
                          <td className="px-4 py-3 text-gray-500">{u.phone}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'}`}>
                              {u.role === 'admin' ? '管理员' : '普通用户'}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`flex items-center gap-1 ${u.status === 1 ? 'text-green-600' : 'text-red-500'}`}>
                              <div className={`w-1.5 h-1.5 rounded-full ${u.status === 1 ? 'bg-green-600' : 'bg-red-500'}`}></div>
                              {u.status === 1 ? '正常' : '禁用'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button onClick={() => { setEditingUser(u); setShowUserModal(true); }} className="text-blue-600 hover:text-blue-800 p-1"><Edit2 size={16}/></button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

              {/* 专家筛选列表 UI 已移除，直接使用账号管理 */}
            

            {/* 批量导入 - 仅管理员可见 */}
            {user.role === 'admin' && (
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2"><Upload className="text-blue-600" size={20}/> 批量导入门店数据</h2>
                <div className="space-y-4">
                  <div className="p-4 bg-blue-50 text-blue-800 text-sm rounded-lg border border-blue-100">
                    <p className="font-bold mb-1">导入格式说明 (支持 Excel 直接粘贴)</p>
                    <p className="text-xs opacity-90 leading-relaxed">
                      请严格按照以下顺序排列列：<br/>
                      1. 门店ID | 2. 门店名称 | 3. 品牌 | 4. 省份 | 5. 城市 | 6. 负责专家 | 7. 频次 | 8. 特殊需求 | 9. 导入状态(是/否)
                    </p>
                  </div>
                  <textarea value={csvText} onChange={(e) => setCsvText(e.target.value)} placeholder="在此处粘贴 Excel 数据 (ID, 名称, 品牌, 省份, 城市, 专家, 频次, 需求, 导入状态)..." className="w-full h-24 p-3 border border-gray-300 rounded-lg text-sm font-mono outline-none"/>
                  <button onClick={handleImport} className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-blue-700">确认导入 / 更新</button>
                </div>
            </div>
            )}

            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="px-4 py-4 border-b border-gray-200 bg-gray-50 flex flex-col gap-4 rounded-t-xl">
                <div className="flex justify-between items-center">
                  <h3 className="font-bold text-gray-700">门店库 ({filteredStores.length})</h3>
                  <div className="flex items-center gap-2">
                    {(!adminFilterProvince.includes('全部') || !adminFilterCity.includes('全部') || !adminFilterBrand.includes('全部') || !adminFilterExpert.includes('全部') || adminFilterImportStatus !== '否' || adminFilterSpecialRequirements !== '全部' || adminSearchTerm) && (
                      <button 
                        onClick={() => {
                          setAdminFilterProvince(['全部']);
                          setAdminFilterCity(['全部']);
                          setAdminFilterBrand(['全部']);
                          setAdminFilterExpert(['全部']);
                          setAdminFilterImportStatus('否');
                          setAdminFilterSpecialRequirements('全部');
                          setAdminSearchTerm('');
                        }}
                        className="text-xs text-red-500 hover:underline"
                      >
                        清空筛选
                      </button>
                    )}
                    <button onClick={handleExport} className="flex items-center gap-2 bg-white border border-gray-300 px-3 py-1.5 rounded-lg text-sm"><Download size={16}/> 导出</button>
                  </div>
                </div>
                
                <div className="flex flex-col gap-3">
                  <div className="flex items-center bg-white border rounded px-2"><Search size={16} className="text-gray-400"/><input type="text" placeholder="搜索名称或ID..." value={adminSearchTerm} onChange={(e) => setAdminSearchTerm(e.target.value)} className="p-2 w-full outline-none text-sm"/></div>
                  
                  <div className="flex flex-wrap gap-2 items-center">
                    <div className="flex flex-col gap-1 min-w-[140px]">
                      <span className="text-[10px] text-gray-400 font-bold uppercase">是否导入</span>
                      <select 
                        value={adminFilterImportStatus} 
                        onChange={(e) => setAdminFilterImportStatus(e.target.value)} 
                        className="p-2 border rounded text-sm bg-white"
                      >
                        <option value="否">否 (默认)</option>
                        <option value="是">是</option>
                        <option value="全部">全部</option>
                      </select>
                    </div>

                    <MultiSelect
                      label="省份"
                      options={uniqueProvinces}
                      value={adminFilterProvince}
                      onChange={setAdminFilterProvince}
                    />

                    <MultiSelect
                      label="城市"
                      options={uniqueCities}
                      value={adminFilterCity}
                      onChange={setAdminFilterCity}
                    />

                    <MultiSelect
                      label="品牌"
                      options={uniqueBrands}
                      value={adminFilterBrand}
                      onChange={setAdminFilterBrand}
                    />

                    <MultiSelect
                      label="专家"
                      options={filterOptionsExperts}
                      value={adminFilterExpert}
                      onChange={setAdminFilterExpert}
                    />

                    <div className="flex flex-col gap-1 min-w-[140px]">
                      <span className="text-[10px] text-gray-400 font-bold uppercase">特殊需求</span>
                      <select
                        value={adminFilterSpecialRequirements}
                        onChange={(e) => setAdminFilterSpecialRequirements(e.target.value as any)}
                        className="p-2 border rounded text-sm bg-white"
                      >
                        <option value="全部">全部</option>
                        <option value="有">仅显示有</option>
                        <option value="无">仅显示无</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <div className="hidden md:block overflow-x-auto rounded-b-xl">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b">
                    <tr>
                      <th className="px-4 py-3">门店ID</th>
                      <th className="px-4 py-3">门店名称</th>
                      <th className="px-4 py-3">品牌</th>
                      <th className="px-4 py-3">省份</th>
                      <th className="px-4 py-3">城市</th>
                      <th className="px-4 py-3 text-center">频次</th>
                      <th className="px-4 py-3">负责专家</th>
                      <th className="px-4 py-3">特殊需求</th>
                      <th className="px-4 py-3">导入状态</th>
                      <th className="px-4 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>{filteredStores.map((store) => (
                    <tr key={store.id} className={`bg-white border-b hover:bg-gray-50 group ${store.deletedAt ? 'opacity-60' : ''}`}>
                      <td className="px-4 py-4 font-mono text-xs text-gray-500">{store.id}</td>
                      <td className="px-4 py-4 font-medium">{store.name}</td>
                      <td className="px-4 py-4"><span className="bg-gray-100 px-2 py-1 rounded text-[10px] font-bold">{store.brand}</span></td>
                      <td className="px-4 py-4 text-gray-600">{store.province || '-'}</td>
                      <td className="px-4 py-4 text-gray-600">{store.city}</td>
                      <td className="px-4 py-4 text-center font-medium text-blue-600">{store.monthlyFrequency}次/月</td>
                      <td className="px-4 py-4 font-medium">{store.assignedExpert || <span className="text-red-500 text-xs italic">待分配</span>}</td>
                      <td className="px-4 py-4 text-xs text-gray-400 max-w-[150px] truncate" title={store.specialRequirements}>{store.specialRequirements || '-'}</td>
                      <td className="px-4 py-4 text-xs">
                        {store.importStatus ? (
                           <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${store.importStatus === '是' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>{store.importStatus}</span>
                        ) : <span className="text-gray-300">-</span>}
                      </td>
                      <td className="px-4 py-4 text-right">
                        <div className="flex justify-end gap-2">
                          <button onClick={() => setEditingStore(store)} className="text-blue-600 hover:bg-blue-50 p-1.5 rounded-lg transition"><Edit2 size={16}/></button>
                          {user.role === 'admin' && (
                            <button onClick={() => openMonthPlanModalForStore(store)} className="text-indigo-700 hover:bg-indigo-50 p-1.5 rounded-lg transition"><Clock size={16}/></button>
                          )}
                          {user.role === 'admin' && (
                            store.deletedAt
                              ? <button onClick={() => handleRestoreStore(store.id)} className="text-green-700 hover:bg-green-50 p-1.5 rounded-lg transition"><RotateCcw size={16}/></button>
                              : <button onClick={() => handleArchiveStore(store.id)} className="text-red-600 hover:bg-red-50 p-1.5 rounded-lg transition"><Trash2 size={16}/></button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>

              <div className="md:hidden bg-gray-50 p-4 space-y-3">
                {filteredStores.map(store => (
                  <div key={store.id} className={`bg-white p-4 rounded-lg shadow-sm border border-gray-100 ${store.deletedAt ? 'opacity-60' : ''}`}>
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div className="font-bold text-gray-900 text-lg">{store.name}</div>
                        <div className="text-xs text-gray-400 font-mono mt-0.5">{store.id}</div>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${store.assignedExpert ? 'bg-indigo-50 text-indigo-700' : 'bg-red-50 text-red-600'}`}>
                        {store.assignedExpert || '待分配'}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm text-gray-600 mb-3">
                      <div className="flex items-center gap-1"><Briefcase size={14}/> {store.brand}</div>
                      <div className="flex items-center gap-1"><MapPin size={14}/> {store.province || '-'}</div>
                      <div className="flex items-center gap-1"><MapPin size={14}/> {store.city}</div>
                      <div className="flex items-center gap-1"><Clock size={14}/> {store.monthlyFrequency}次/月</div>
                      <div className="flex items-center gap-1"><Tag size={14}/> {store.specialRequirements || '无'}</div>
                    </div>
                    <div className="flex justify-end gap-3 border-t border-gray-50 pt-3">
                      <button onClick={() => setEditingStore(store)} className="flex items-center gap-1 text-sm text-blue-600 bg-blue-50 px-3 py-1.5 rounded-md">
                        <Edit2 size={14}/> 编辑
                      </button>
                      {user.role === 'admin' && (
                        <button onClick={() => openMonthPlanModalForStore(store)} className="flex items-center gap-1 text-sm text-indigo-700 bg-indigo-50 px-3 py-1.5 rounded-md">
                          <Clock size={14}/> 本月计划
                        </button>
                      )}
                      {user.role === 'admin' && (
                        <button onClick={() => handleArchiveStore(store.id)} className="flex items-center gap-1 text-sm text-red-600 bg-red-50 px-3 py-1.5 rounded-md">
                          <Trash2 size={14}/> 停用
                        </button>
                      )}
                      {user.role === 'admin' && store.deletedAt && (
                        <button onClick={() => handleRestoreStore(store.id)} className="flex items-center gap-1 text-sm text-green-700 bg-green-50 px-3 py-1.5 rounded-md">
                          <RotateCcw size={14}/> 恢复
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

            </div>
          </div>
        )}

        {activeTab === 'calendar' && (
          <div className="flex flex-col lg:flex-row gap-6 h-full animate-in fade-in duration-300 overflow-hidden relative">
            <div className="hidden lg:flex lg:w-72 w-full flex-shrink-0 flex-col bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="p-4 bg-gray-50 border-b border-gray-200">
                  <h3 className="font-bold text-gray-800 flex items-center justify-between"><span>待安排门店</span><span className="bg-orange-100 text-orange-800 text-xs px-2 py-1 rounded-full">{unscheduledStores.length}</span></h3>
                  <p className="text-xs text-gray-500 mt-1">
                    {isPastMonthView ? '历史月份仅用于查看，不显示待排门店' : `${currentUser} ${formatMonthKey(currentDate)} 待排门店 (仅显示未导入门店)`}
                  </p>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
                  {isPastMonthView && <div className="text-center text-gray-400 py-8 text-xs">切换到当前月或未来月份后，才会显示待排门店</div>}
                  {!isPastMonthView && unscheduledStores.length === 0 && <div className="text-center text-gray-400 py-8 text-xs">没有未导入的待办任务</div>}
                  {!isPastMonthView && unscheduledStores.map(store => {
                    const isSelected = selectedStoreIds.includes(store.id);
                    return (
                      <div 
                        key={store.id} 
                        onClick={() => toggleStoreSelection(store.id)} 
                        draggable
                        onDragStart={beginStoreDrag(store.id)}
                        onDragEnd={handleDragEnd}
                        className={`bg-white p-3 rounded-lg border shadow-sm cursor-pointer transition select-none
                          ${isSelected ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-gray-200 hover:border-blue-300'}
                          ${dragging?.kind === 'store' && dragging.id === store.id ? 'opacity-50' : ''}
                        `}
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className="font-medium text-gray-900 whitespace-normal break-words leading-tight">{store.name}</span>
                          {isSelected ? <CheckSquare size={16} className="text-blue-600 flex-shrink-0 ml-2"/> : <Square size={16} className="text-gray-300 flex-shrink-0 ml-2"/>}
                        </div>
                        <div className="flex justify-between text-xs text-gray-400 mt-2 items-center">
                          <span className="bg-gray-100 px-1 rounded">{store.city}</span>
                          <span className={`px-1.5 py-0.5 rounded font-medium ${store.plannedCount >= store.targetFrequency ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
                            进度: {store.plannedCount}/{store.targetFrequency}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="p-3 border-t border-gray-200 bg-gray-50">
                  <button 
                    onClick={handleBatchAddVisits}
                    disabled={isPastMonthView || selectedStoreIds.length === 0}
                    className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    <Plus size={16}/> 
                    {isPastMonthView ? '历史月份不可排' : (selectedStoreIds.length > 0 ? `批量添加 (${selectedStoreIds.length})` : '请选择门店')}
                  </button>
                  <p className="text-[10px] text-center text-gray-400 mt-2">提示：选中左侧门店后，点击按钮批量加到当前选中日期</p>
                </div>
            </div>

            <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col overflow-hidden relative">
              <div className="p-4 border-b border-gray-200 bg-white">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-lg font-bold text-gray-800 flex flex-col sm:flex-row sm:items-center sm:gap-2 leading-tight">
                      <span>{currentDate.getFullYear()}年 {currentDate.getMonth() + 1}月</span>
                      {viewMode === 'week' && <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-normal w-fit mt-1 sm:mt-0">第 {Math.ceil(currentDate.getDate() / 7)} 周</span>}
                    </h2>
                    <div className="flex items-center bg-gray-100 rounded-lg p-0.5 flex-shrink-0">
                      <button onClick={handlePrev} className="p-1.5 hover:bg-white rounded-md transition text-gray-600"><ChevronLeft size={16}/></button>
                      <button onClick={handleNext} className="p-1.5 hover:bg-white rounded-md transition text-gray-600"><ChevronRight size={16}/></button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <button onClick={() => openExtraVisitModal()} className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium bg-orange-50 text-orange-700 hover:bg-orange-100 transition">
                      <Plus size={14}/> 临时上门
                    </button>
                    <div className="flex bg-gray-100 p-1 rounded-lg flex-shrink-0">
                      <button onClick={() => { setViewMode('month'); setShowDetailsModal(false); }} className={`flex items-center gap-1 px-3 py-2 rounded-md text-sm font-medium transition ${viewMode === 'month' ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                        <Grid3X3 size={14}/> 月
                      </button>
                      <button onClick={() => { setViewMode('week'); setShowDetailsModal(false); }} className={`flex items-center gap-1 px-3 py-2 rounded-md text-sm font-medium transition ${viewMode === 'week' ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                        <LayoutList size={14}/> 周
                      </button>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="flex-1 overflow-auto bg-gray-50 relative">
                {viewMode === 'month' ? renderMonthView() : (
                  <>
                    <div className="hidden lg:block h-full">{renderDesktopWeekView()}</div>
                    <div className="lg:hidden h-full">{renderMobileWeekView()}</div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {editingStore && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
           <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
             <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center"><h3 className="font-bold text-gray-800">编辑门店</h3><button onClick={() => setEditingStore(null)}><X size={20}/></button></div>
             <div className="p-6 space-y-4">
               <div className="grid grid-cols-2 gap-4">
                 <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">门店名称</label>
                    {user.role === 'admin' ? (
                      <input type="text" value={editingStore.name} onChange={(e) => setEditingStore({...editingStore, name: e.target.value})} className="w-full p-2 border rounded text-sm"/>
                    ) : (
                      <div className="w-full p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">{editingStore.name}</div>
                    )}
                 </div>
                 <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">品牌</label>
                    {user.role === 'admin' ? (
                      <input type="text" value={editingStore.brand} onChange={(e) => setEditingStore({...editingStore, brand: e.target.value})} className="w-full p-2 border rounded text-sm"/>
                    ) : (
                      <div className="w-full p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">{editingStore.brand}</div>
                    )}
                 </div>
               </div>
               <div className="grid grid-cols-2 gap-4">
                 <div>
                   <label className="block text-sm font-medium text-gray-700 mb-1">省份</label>
                   {user.role === 'admin' ? (
                     <input type="text" value={editingStore.province} onChange={(e) => setEditingStore({...editingStore, province: e.target.value})} className="w-full p-2 border rounded text-sm"/>
                   ) : (
                     <div className="w-full p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">{editingStore.province || '-'}</div>
                   )}
                 </div>
                 <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">城市</label>
                    {user.role === 'admin' ? (
                      <input type="text" value={editingStore.city} onChange={(e) => setEditingStore({...editingStore, city: e.target.value})} className="w-full p-2 border rounded text-sm"/>
                    ) : (
                      <div className="w-full p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">{editingStore.city}</div>
                    )}
                 </div>
                 <div><label className="block text-sm font-medium text-gray-700 mb-1">服务频次</label><input type="number" min="1" value={editingStore.monthlyFrequency} onChange={(e) => setEditingStore({...editingStore, monthlyFrequency: parseInt(e.target.value)})} className="w-full p-2 border rounded text-sm"/></div>
               </div>
               <div><label className="block text-sm font-medium text-gray-700 mb-1">负责专家</label><select value={editingStore.assignedExpert} onChange={(e) => setEditingStore({...editingStore, assignedExpert: e.target.value})} className="w-full p-2 border rounded text-sm bg-white"><option value="">待分配</option>{sortedExperts.map(e=><option key={e} value={e}>{e}</option>)}</select></div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">特殊需求</label>
                {user.role === 'admin' ? (
                  <textarea rows={2} value={editingStore.specialRequirements} onChange={(e) => setEditingStore({...editingStore, specialRequirements: e.target.value})} className="w-full p-2 border rounded text-sm"/>
                ) : (
                  <div className="w-full p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600 whitespace-pre-wrap">{editingStore.specialRequirements || '-'}</div>
                )}
              </div>
               <div>
                   <label className="block text-sm font-medium text-gray-700 mb-1">导入状态</label>
                   {user.role === 'admin' ? (
                   <select 
                     value={editingStore.importStatus || ''} 
                     onChange={(e) => setEditingStore({...editingStore, importStatus: e.target.value as any})} 
                     className="w-full p-2 border rounded text-sm bg-white"
                   >
                     <option value="">(空)</option>
                     <option value="是">是</option>
                     <option value="否">否</option>
                   </select>
                   ) : (
                     <div className="w-full p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">{editingStore.importStatus || '(空)'}</div>
                   )}
                </div>
               <div><button onClick={handleSaveEdit} className="w-full bg-blue-600 text-white py-2 rounded-lg mt-2 font-bold shadow-lg shadow-blue-200">保存修改</button></div>
             </div>
           </div>
        </div>
      )}

      {showUserModal && editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
              <h3 className="font-bold text-gray-800">{editingUser.id ? '编辑账号' : '新增账号'}</h3>
              <button onClick={() => { setShowUserModal(false); setEditingUser(null); }}><X size={20}/></button>
            </div>
            <form onSubmit={handleSaveManagedUser} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">真实姓名</label>
                <input 
                  type="text" 
                  required 
                  className="w-full p-2 border rounded text-sm"
                  value={editingUser.name || ''}
                  onChange={e => setEditingUser({...editingUser, name: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">手机号</label>
                <input 
                  type="tel" 
                  required 
                  className="w-full p-2 border rounded text-sm"
                  value={editingUser.phone || ''}
                  onChange={e => setEditingUser({...editingUser, phone: e.target.value})}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{editingUser.id ? '重置密码 (留空则不修改)' : '初始密码'}</label>
                <input 
                  type="password" 
                  required={!editingUser.id}
                  className="w-full p-2 border rounded text-sm"
                  placeholder="8位以上含大小写字母+数字"
                  value={editingUser.password || ''}
                  onChange={e => setEditingUser({...editingUser, password: e.target.value})}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">权限角色</label>
                  <select 
                    className="w-full p-2 border rounded text-sm bg-white"
                    value={editingUser.role || 'user'}
                    onChange={e => setEditingUser({...editingUser, role: e.target.value})}
                  >
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">账号状态</label>
                  <select 
                    className="w-full p-2 border rounded text-sm bg-white"
                    value={editingUser.status}
                    onChange={e => setEditingUser({...editingUser, status: parseInt(e.target.value)})}
                  >
                    <option value={1}>启用</option>
                    <option value={0}>禁用</option>
                  </select>
                </div>
              </div>
              <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded-lg mt-2 font-bold">保存账号</button>
            </form>
          </div>
        </div>
      )}

      {/* 统一详情与操作弹窗：只要选中某天，就会触发详情面板。在此面板中直接进行管理或调用增加操作 */}
      {showDetailsModal && selectedDateForVisit && !showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden flex flex-col max-h-[85vh]">
             <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center bg-blue-50">
               <div><h3 className="font-bold text-gray-800">{selectedDateForVisit} 工作安排</h3></div>
               <button onClick={() => setShowDetailsModal(false)} className="p-1 hover:bg-white/50 rounded-full"><X size={20}/></button>
            </div>
            <div className="p-4 overflow-y-auto">
               <div className="space-y-2">
                 {visitsForSelectedDate.length === 0 ? <div className="text-gray-400 text-center py-4">该日暂无安排</div> : visitsForSelectedDate.map(v => {
                   const s = stores.find(store => store.id === v.storeId);
                   return (
                     <div key={v.id} className="flex justify-between items-center bg-gray-50 p-2 rounded border border-gray-100">
                      <div className="min-w-0 pr-2">
                        <div className="font-medium whitespace-normal break-words leading-tight">{s?.name}</div>
                        {v.type === 'extra' && <div className="text-[10px] text-orange-700 mt-0.5 whitespace-normal break-words leading-tight">临时：{v.title || '-'}</div>}
                      </div>
                       <button onClick={(e) => handleRemoveVisit(v.id, e)} className="text-red-500 flex-shrink-0 ml-2"><Trash2 size={16}/></button>
                     </div>
                   )
                 })}
               </div>
               <div className="mt-4 pt-4 border-t border-gray-100">
                <div className="space-y-2">
                  <button onClick={() => setShowAddModal(true)} className="w-full py-2 bg-blue-600 text-white rounded-lg flex items-center justify-center gap-2"><Plus size={16}/> 增加门店计划</button>
                  <button onClick={() => openExtraVisitModal(selectedDateForVisit)} className="w-full py-2 bg-orange-600 text-white rounded-lg flex items-center justify-center gap-2"><Plus size={16}/> 新增临时上门</button>
                </div>
               </div>
            </div>
          </div>
        </div>
      )}

      {/* 手机端安排任务(选择门店库)弹窗 */}
      {showAddModal && (
        <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white w-full sm:max-w-md rounded-t-xl sm:rounded-xl shadow-2xl flex flex-col max-h-[80vh]">
            <div className="p-4 border-b border-gray-200 flex justify-between items-center bg-gray-50 rounded-t-xl">
              <div><h3 className="font-bold text-lg text-gray-900">选择要安排的门店</h3><p className="text-xs text-gray-500">{selectedDateForVisit ? `已选: ${selectedDateForVisit}` : '默认: 今天'} (仅显示未导入)</p></div>
              <button onClick={() => setShowAddModal(false)} className="bg-gray-200 p-1 rounded-full"><X size={20}/></button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50 pb-20">
              {isPastMonthView ? (
                <div className="text-center py-8 text-gray-400">历史月份不显示待排门店</div>
              ) : unscheduledStores.length === 0 ? (
                <div className="text-center py-8 text-gray-400">所有未导入门店任务已安排！</div>
              ) : unscheduledStores.map(store => {
                  const isSelected = selectedStoreIds.includes(store.id);
                  return (
                    <div 
                      key={store.id} 
                      onClick={() => toggleStoreSelection(store.id)} 
                      className={`bg-white p-4 rounded-lg border shadow-sm active:scale-95 transition flex justify-between items-center cursor-pointer
                        ${isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}
                      `}
                    >
                      <div>
                        <div className="font-bold text-gray-800 whitespace-normal break-words leading-tight">{store.name}</div>
                        <div className="text-xs text-gray-500 mt-1 flex gap-2">
                          <span>{store.city}</span>
                          <span className={`${store.plannedCount >= store.targetFrequency ? 'text-green-600' : 'text-blue-600'}`}>
                            进度: {store.plannedCount}/{store.targetFrequency}
                          </span>
                        </div>
                      </div>
                      <div className={`w-6 h-6 rounded border flex items-center justify-center flex-shrink-0 ml-2 ${isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-300'}`}>
                        {isSelected && <CheckSquare size={14} className="text-white"/>}
                      </div>
                    </div>
                  );
              })}
            </div>

            <div className="p-4 border-t border-gray-200 bg-white absolute bottom-0 left-0 right-0 rounded-b-xl">
              <button 
                onClick={handleBatchAddVisits}
                disabled={isPastMonthView || selectedStoreIds.length === 0}
                className="w-full bg-blue-600 text-white py-3 rounded-lg text-base font-bold shadow-md active:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isPastMonthView ? '历史月份不可排' : (selectedStoreIds.length > 0 ? `确认添加 ${selectedStoreIds.length} 个门店` : '请选择门店')}
              </button>
            </div>
          </div>
        </div>
      )}

      {showMonthPlanModal && monthPlanStore && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
              <div>
                <div className="font-bold text-gray-800">本月计划</div>
                <div className="text-xs text-gray-500 mt-1">{monthPlanStore.name} · {formatMonthKey(currentDate)}</div>
              </div>
              <button onClick={() => { setShowMonthPlanModal(false); setMonthPlanStore(null); }}><X size={20}/></button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">本月目标次数</label>
                <input type="number" min="0" value={monthPlanTarget} onChange={(e) => setMonthPlanTarget(parseInt(e.target.value) || 0)} className="w-full p-2 border rounded text-sm"/>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">原因</label>
                <textarea rows={3} value={monthPlanReason} onChange={(e) => setMonthPlanReason(e.target.value)} className="w-full p-2 border rounded text-sm"/>
              </div>
              <div className="flex gap-2">
                <button onClick={() => { setShowMonthPlanModal(false); setMonthPlanStore(null); }} className="flex-1 bg-gray-100 text-gray-700 py-2 rounded-lg text-sm font-medium">取消</button>
                <button onClick={handleSaveMonthPlan} className="flex-1 bg-blue-600 text-white py-2 rounded-lg text-sm font-medium">保存</button>
              </div>
              {monthPlans[monthPlanStore.id] && (
                <button onClick={handleClearMonthPlan} className="w-full bg-white text-red-600 py-2 rounded-lg text-sm font-medium border border-red-200">清除本月覆盖</button>
              )}
            </div>
          </div>
        </div>
      )}

      {showExtraModal && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
              <div className="font-bold text-gray-800">新增临时上门</div>
              <button onClick={() => setShowExtraModal(false)}><X size={20}/></button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">日期</label>
                  <input type="date" value={extraDate} onChange={(e) => setExtraDate(e.target.value)} className="w-full p-2 border rounded text-sm"/>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">门店搜索</label>
                  <input type="text" value={extraSearchTerm} onChange={(e) => setExtraSearchTerm(e.target.value)} className="w-full p-2 border rounded text-sm" placeholder="输入门店名/ID"/>
                </div>
              </div>
              <div className="border rounded-lg max-h-48 overflow-y-auto">
                {(stores
                  .filter(s => {
                    const q = extraSearchTerm.trim().toLowerCase();
                    if (!q) return true;
                    return s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q);
                  })
                  .slice(0, 30)
                ).map(s => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setExtraStoreId(s.id)}
                    className={`w-full text-left px-3 py-2 text-sm border-b last:border-b-0 hover:bg-gray-50 ${extraStoreId === s.id ? 'bg-orange-50' : 'bg-white'}`}
                  >
                    <div className="font-medium text-gray-800 whitespace-normal break-words leading-tight">{s.name}</div>
                    <div className="text-[10px] text-gray-500 mt-0.5">{s.id} · {s.brand || '-'} · {s.city}</div>
                  </button>
                ))}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">上门原因</label>
                <textarea rows={3} value={extraTitle} onChange={(e) => setExtraTitle(e.target.value)} className="w-full p-2 border rounded text-sm" placeholder="例如：报修、复查、紧急处理"/>
              </div>
              {user?.role === 'admin' && (
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={extraCountTowardsTarget} onChange={(e) => setExtraCountTowardsTarget(e.target.checked)} />
                  计入当月目标次数
                </label>
              )}
              <div className="flex gap-2">
                <button onClick={() => setShowExtraModal(false)} className="flex-1 bg-gray-100 text-gray-700 py-2 rounded-lg text-sm font-medium">取消</button>
                <button onClick={handleCreateExtraVisit} className="flex-1 bg-orange-600 text-white py-2 rounded-lg text-sm font-medium">创建</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
