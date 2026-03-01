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
  LogOut
} from 'lucide-react';

import './index.css';

// --- 全局配置 ---
const API_BASE = (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'))
  ? 'http://localhost:3000/api'
  : '/schedule/api';

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
  city: string;
  assignedExpert: string; 
  specialRequirements?: string;
  monthlyFrequency: number; 
  importStatus?: string; // 新增字段
}

interface Visit {
  id: string;
  storeId: string;
  date: string; 
  expertName: string;
  status: 'planned' | 'completed';
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
    return saved ? JSON.parse(saved) : null;
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
  
  // 编辑/导入/筛选状态
  const [csvText, setCsvText] = useState('');
  const [editingStore, setEditingStore] = useState<Store | null>(null); 
  // const [newExpertName, setNewExpertName] = useState(''); // 已移除
  const [adminFilterCity, setAdminFilterCity] = useState<string[]>(['全部']);
  const [adminFilterBrand, setAdminFilterBrand] = useState<string[]>(['全部']);
  const [adminFilterExpert, setAdminFilterExpert] = useState<string[]>(['全部']);
  const [adminFilterImportStatus, setAdminFilterImportStatus] = useState('否'); // 默认显示未导入门店
  const [adminSearchTerm, setAdminSearchTerm] = useState('');

  // --- 辅助函数 ---
  const getDaysInMonth = (year: number, month: number) => new Date(year, month + 1, 0).getDate();
  const getFirstDayOfMonth = (year: number, month: number) => new Date(year, month, 1).getDay();
  const formatDate = (date: Date) => date.toISOString().split('T')[0];
  const formatDateStr = (year: number, month: number, day: number) => {
    return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  };

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
    localStorage.removeItem('auth_user');
    showToast('已退出登录', 'info');
  };

  // --- API ---
  const authenticatedFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${user?.token}`
    };
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401 || res.status === 403) {
      handleLogout();
      throw new Error('Session expired');
    }
    return res;
  }, [user]);

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

      // 默认选中第一个专家，不再支持“全部”
      if (!currentUser && dataExperts.length > 0) {
        setCurrentUser(dataExperts[0]);
      } else if (currentUser === '全部' && dataExperts.length > 0) {
        // 如果之前选的是“全部”，强制切回第一个专家
        setCurrentUser(dataExperts[0]);
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
      if (!silent) showToast("数据加载失败", 'error');
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [user, currentUser, showToast, authenticatedFetch]);

  useEffect(() => {
    if (user) {
      fetchAllData();
      if (user.role === 'admin') fetchManagedUsers();
    }
  }, [user, fetchAllData, fetchManagedUsers]);

  // --- 逻辑 ---

  const handleDayClick = (dateStr: string) => {
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
    return stores.filter(s => s.importStatus !== '是');
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
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;
    const prefix = `${year}-${String(month).padStart(2, '0')}`;
    const thisMonthVisits = visits.filter(v => v.date.startsWith(prefix) && v.expertName === currentUser);

    return myStores.map(store => {
      const plannedCount = thisMonthVisits.filter(v => v.storeId === store.id).length;
      const remaining = Math.max(0, store.monthlyFrequency - plannedCount);
      return { ...store, remaining, plannedCount };
    }).filter(s => s.remaining > 0);
  }, [myStores, visits, currentDate, currentUser]);

  // [修改] 实现筛选属性的拼音排序和级联联动
  const uniqueCities = useMemo(() => {
    const cities = Array.from(new Set(stores.map(s => s.city))).filter(c => typeof c === 'string' && c.trim() !== '');
    return ['全部', ...cities.sort((a, b) => a.localeCompare(b, 'zh-CN'))];
  }, [stores]);

  const uniqueBrands = useMemo(() => {
    let filtered = stores;
    if (!adminFilterCity.includes('全部')) {
      filtered = filtered.filter(s => adminFilterCity.includes(s.city));
    }
    const brands = Array.from(new Set(filtered.map(s => s.brand))).filter(b => typeof b === 'string' && b.trim() !== '');
    return ['全部', ...brands.sort((a, b) => a.localeCompare(b, 'zh-CN'))];
  }, [stores, adminFilterCity]);

  const sortedExperts = useMemo(() => {
    // 过滤非字符串数据，防止 localeCompare 报错
    return experts.filter(e => typeof e === 'string').sort((a, b) => a.localeCompare(b, 'zh-CN'));
  }, [experts]);

  // [新增] 当联动筛选导致当前选中项无效时，自动重置
  useEffect(() => {
    if (!adminFilterCity.includes('全部')) {
        // 简单逻辑：如果筛选城市变了，品牌可能不再有效，重置品牌
        // 更复杂的逻辑是检查当前选中的品牌是否还在 uniqueBrands 中
        const validBrands = uniqueBrands;
        const isValid = adminFilterBrand.every(b => validBrands.includes(b));
        if (!isValid) setAdminFilterBrand(['全部']);
    }
  }, [uniqueBrands, adminFilterCity, adminFilterBrand]);

  const filteredStores = useMemo(() => {
    return stores.filter(store => {
      const matchCity = adminFilterCity.includes('全部') || adminFilterCity.includes(store.city);
      const matchBrand = adminFilterBrand.includes('全部') || adminFilterBrand.includes(store.brand);
      
      let matchExpert = true;
      if (adminFilterExpert.includes('全部')) {
        matchExpert = true;
      } else {
        const hasUnassigned = adminFilterExpert.includes('待分配');
        const hasSpecific = adminFilterExpert.some(e => e !== '待分配' && e !== '全部');
        
        if (hasUnassigned && !store.assignedExpert) matchExpert = true;
        else if (hasSpecific && adminFilterExpert.includes(store.assignedExpert)) matchExpert = true;
        else matchExpert = false;
      }
      
      const matchImportStatus = 
        adminFilterImportStatus === '全部' || 
        (adminFilterImportStatus === '是' ? store.importStatus === '是' : store.importStatus !== '是');

      const searchLower = adminSearchTerm.toLowerCase();
      const matchSearch = store.name.toLowerCase().includes(searchLower) || store.id.toLowerCase().includes(searchLower);
      return matchCity && matchBrand && matchExpert && matchImportStatus && matchSearch;
    });
  }, [stores, adminFilterCity, adminFilterBrand, adminFilterExpert, adminFilterImportStatus, adminSearchTerm]);

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
        
        // 严格按照 8 列顺序：1. ID, 2. 名称, 3. 品牌, 4. 城市, 5. 专家, 6. 频次, 7. 需求, 8. 导入状态
        const id = cols[0];
        const name = cols[1];
        const brand = cols[2];
        // const province = cols[3]; // 已移除
        const city = cols[3];
        const assignedExpert = cols[4] || '';
        
        if (!id || !name || !city) {
          console.warn(`跳过无效行 ${i + 1}: ID, 名称, 城市 不能为空`, cols);
          continue;
        }

        let frequency = 1;
        if (cols[5]) {
          const parsed = parseInt(cols[5]);
          if (!isNaN(parsed) && parsed > 0) frequency = parsed;
        }
        
        const specialRequirements = cols[6] || '';
        const importStatus = cols[7] || ''; // 新增字段解析

        newStores.push({
          id, name, brand, city,
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
    let csvContent = "\ufeff门店ID,门店名称,品牌,城市,负责专家,服务频次,特殊需求,导入状态\n";
    stores.forEach(store => {
      const row = [
        store.id, 
        store.name, 
        store.brand || '', 
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

  const handleDeleteStore = async (id: string) => {
    if(!confirm('确定删除?')) return;
    try {
      const res = await authenticatedFetch(`${API_BASE}/stores/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setStores(stores.filter(s => s.id !== id));
        setVisits(visits.filter(v => v.storeId !== id)); 
        showToast('已删除', 'info');
      }
    } catch (e) { console.error(e); }
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

      days.push(
        <div 
          key={dateStr} 
          onClick={() => handleDayClick(dateStr)} 
          className={`min-h-[6rem] p-1 border-r border-b border-gray-200 relative cursor-pointer transition-colors 
            ${isSelected ? 'bg-blue-100 ring-2 ring-inset ring-blue-400' : isToday ? 'bg-blue-50/30' : 'bg-white hover:bg-gray-50'}
          `}
        >
          <div className="flex justify-between items-start">
            <span className={`text-sm font-medium w-6 h-6 flex items-center justify-center rounded-full ${isToday ? 'bg-blue-600 text-white' : 'text-gray-700'}`}>{d}</span>
            {hasVisits && (<span className="hidden md:inline-block text-xs bg-green-100 text-green-800 px-1 rounded scale-90 origin-top-right">{dayVisits.length} 次</span>)}
          </div>
          <div className="hidden md:block mt-1 space-y-1 overflow-y-auto max-h-[4.5rem] no-scrollbar">
            {dayVisits.slice(0, 3).map(visit => {
              const store = stores.find(s => s.id === visit.storeId);
              return (
                // [修改] 加入原生 tooltip，允许换行显示避免文字被阶段
                <div key={visit.id} title={`${store?.name} (${store?.brand} · ${store?.city})`} className="whitespace-normal break-words line-clamp-2 leading-tight text-[10px] bg-blue-100 text-blue-900 p-0.5 rounded px-1 mb-0.5">
                  {store?.name}
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

      weekDays.push(
        <div 
          key={dateStr} 
          onClick={() => handleDayClick(dateStr)}
          className={`flex-1 flex flex-col min-w-[140px] border-r border-gray-200 
            ${isSelected ? 'bg-blue-50 ring-2 ring-inset ring-blue-300' : isToday ? 'bg-blue-50/20' : 'bg-white'}
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
                return (
                  <div key={visit.id} className="relative group bg-white border-l-4 border-l-blue-500 shadow-sm border border-gray-200 rounded p-2 hover:shadow-md transition">
                    {/* [修改] 移除 truncate，允许店名完整换行显示，并增加原生 tooltip */}
                    <div className="font-bold text-gray-800 text-sm whitespace-normal break-words leading-snug pr-4" title={`${store?.name} (${store?.brand} · ${store?.city})`}>{store?.name}</div>
                    <div className="flex items-center gap-1 text-[10px] text-gray-500 mt-1"><MapPin size={10}/> {store?.city}</div>
                    <button onClick={(e) => handleRemoveVisit(visit.id, e)} className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition"><X size={12}/></button>
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

      weekRows.push(
        <div key={dateStr} onClick={() => handleDayClick(dateStr)} className={`flex flex-col border-b border-gray-100 p-3 cursor-pointer ${isSelected ? 'bg-blue-50' : 'bg-white'}`}>
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
                return (
                  <div key={visit.id} className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm flex justify-between items-center">
                    <div>
                      <div className="font-bold text-gray-800 text-sm whitespace-normal break-words leading-snug">{store?.name}</div>
                      <div className="text-xs text-gray-500 mt-1">{store?.brand} · {store?.city}</div>
                    </div>
                    <button onClick={(e) => handleRemoveVisit(visit.id, e)} className="p-2 text-gray-400 hover:text-red-500"><X size={18}/></button>
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

      <nav className="bg-white border-b border-gray-200 px-4 py-3 sticky top-0 z-20 shadow-sm">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="bg-blue-600 p-1.5 rounded-lg text-white"><Calendar size={20} /></div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight hidden sm:block">ServiceMate</h1>
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
                      1. 门店ID | 2. 门店名称 | 3. 品牌 | 4. 城市 | 5. 负责专家 | 6. 频次 | 7. 特殊需求 | 8. 导入状态(是/否)
                    </p>
                  </div>
                  <textarea value={csvText} onChange={(e) => setCsvText(e.target.value)} placeholder="在此处粘贴 Excel 数据 (ID, 名称, 品牌, 城市, 专家, 频次, 需求, 导入状态)..." className="w-full h-24 p-3 border border-gray-300 rounded-lg text-sm font-mono outline-none"/>
                  <button onClick={handleImport} className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-blue-700">确认导入 / 更新</button>
                </div>
            </div>
            )}

            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="px-4 py-4 border-b border-gray-200 bg-gray-50 flex flex-col gap-4 rounded-t-xl">
                <div className="flex justify-between items-center">
                  <h3 className="font-bold text-gray-700">门店库 ({filteredStores.length})</h3>
                  <div className="flex items-center gap-2">
                    {(!adminFilterCity.includes('全部') || !adminFilterBrand.includes('全部') || !adminFilterExpert.includes('全部') || adminFilterImportStatus !== '否' || adminSearchTerm) && (
                      <button 
                        onClick={() => {
                          setAdminFilterCity(['全部']);
                          setAdminFilterBrand(['全部']);
                          setAdminFilterExpert(['全部']);
                          setAdminFilterImportStatus('否');
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
                      options={['全部', '待分配', ...sortedExperts]}
                      value={adminFilterExpert}
                      onChange={setAdminFilterExpert}
                    />
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
                      <th className="px-4 py-3">城市</th>
                      <th className="px-4 py-3 text-center">频次</th>
                      <th className="px-4 py-3">负责专家</th>
                      <th className="px-4 py-3">特殊需求</th>
                      <th className="px-4 py-3">导入状态</th>
                      <th className="px-4 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>{filteredStores.map((store) => (
                    <tr key={store.id} className="bg-white border-b hover:bg-gray-50 group">
                      <td className="px-4 py-4 font-mono text-xs text-gray-500">{store.id}</td>
                      <td className="px-4 py-4 font-medium">{store.name}</td>
                      <td className="px-4 py-4"><span className="bg-gray-100 px-2 py-1 rounded text-[10px] font-bold">{store.brand}</span></td>
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
                            <button onClick={() => handleDeleteStore(store.id)} className="text-red-600 hover:bg-red-50 p-1.5 rounded-lg transition"><Trash2 size={16}/></button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>

              <div className="md:hidden bg-gray-50 p-4 space-y-3">
                {filteredStores.map(store => (
                  <div key={store.id} className="bg-white p-4 rounded-lg shadow-sm border border-gray-100">
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
                      <div className="flex items-center gap-1"><MapPin size={14}/> {store.city}</div>
                      <div className="flex items-center gap-1"><Clock size={14}/> {store.monthlyFrequency}次/月</div>
                      <div className="flex items-center gap-1"><Tag size={14}/> {store.specialRequirements || '无'}</div>
                    </div>
                    <div className="flex justify-end gap-3 border-t border-gray-50 pt-3">
                      <button onClick={() => setEditingStore(store)} className="flex items-center gap-1 text-sm text-blue-600 bg-blue-50 px-3 py-1.5 rounded-md">
                        <Edit2 size={14}/> 编辑
                      </button>
                      {user.role === 'admin' && (
                        <button onClick={() => handleDeleteStore(store.id)} className="flex items-center gap-1 text-sm text-red-600 bg-red-50 px-3 py-1.5 rounded-md">
                          <Trash2 size={14}/> 删除
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
                  <p className="text-xs text-gray-500 mt-1">{currentUser} 本月剩余任务 (仅显示未导入门店)</p>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
                  {unscheduledStores.length === 0 && <div className="text-center text-gray-400 py-8 text-xs">没有未导入的待办任务</div>}
                  {unscheduledStores.map(store => {
                    const isSelected = selectedStoreIds.includes(store.id);
                    return (
                      <div 
                        key={store.id} 
                        onClick={() => toggleStoreSelection(store.id)} 
                        className={`bg-white p-3 rounded-lg border shadow-sm cursor-pointer transition select-none
                          ${isSelected ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-gray-200 hover:border-blue-300'}
                        `}
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className="font-medium text-gray-900 whitespace-normal break-words leading-tight">{store.name}</span>
                          {isSelected ? <CheckSquare size={16} className="text-blue-600 flex-shrink-0 ml-2"/> : <Square size={16} className="text-gray-300 flex-shrink-0 ml-2"/>}
                        </div>
                        <div className="flex justify-between text-xs text-gray-400 mt-2 items-center">
                          <span className="bg-gray-100 px-1 rounded">{store.city}</span>
                          <span className={`px-1.5 py-0.5 rounded font-medium ${store.plannedCount >= store.monthlyFrequency ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
                            进度: {store.plannedCount}/{store.monthlyFrequency}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="p-3 border-t border-gray-200 bg-gray-50">
                  <button 
                    onClick={handleBatchAddVisits}
                    disabled={selectedStoreIds.length === 0}
                    className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    <Plus size={16}/> 
                    {selectedStoreIds.length > 0 ? `批量添加 (${selectedStoreIds.length})` : '请选择门店'}
                  </button>
                  <p className="text-[10px] text-center text-gray-400 mt-2">提示：选中左侧门店后，点击按钮批量加到当前选中日期</p>
                </div>
            </div>

            <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col overflow-hidden relative">
              <div className="p-4 border-b border-gray-200 flex justify-between items-center bg-white">
                 <div className="flex items-center gap-4">
                   <div>
                     <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                       {currentDate.getFullYear()}年 {currentDate.getMonth() + 1}月
                       {viewMode === 'week' && <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-normal">第 {Math.ceil(currentDate.getDate() / 7)} 周</span>}
                     </h2>
                   </div>
                   <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
                     <button onClick={handlePrev} className="p-1.5 hover:bg-white rounded-md transition text-gray-600"><ChevronLeft size={16}/></button>
                     <button onClick={handleNext} className="p-1.5 hover:bg-white rounded-md transition text-gray-600"><ChevronRight size={16}/></button>
                   </div>
                 </div>
                 
                 <div className="flex bg-gray-100 p-1 rounded-lg">
                   <button onClick={() => { setViewMode('month'); setShowDetailsModal(false); }} className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-sm font-medium transition ${viewMode === 'month' ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                     <Grid3X3 size={14}/> 月
                   </button>
                   <button onClick={() => { setViewMode('week'); setShowDetailsModal(false); }} className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-sm font-medium transition ${viewMode === 'week' ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                     <LayoutList size={14}/> 周
                   </button>
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
               <div><label className="block text-sm font-medium text-gray-700 mb-1">特殊需求</label><textarea rows={2} value={editingStore.specialRequirements} onChange={(e) => setEditingStore({...editingStore, specialRequirements: e.target.value})} className="w-full p-2 border rounded text-sm"/></div>
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
                       <span className="font-medium whitespace-normal break-words leading-tight">{s?.name}</span>
                       <button onClick={(e) => handleRemoveVisit(v.id, e)} className="text-red-500 flex-shrink-0 ml-2"><Trash2 size={16}/></button>
                     </div>
                   )
                 })}
               </div>
               <div className="mt-4 pt-4 border-t border-gray-100">
                 <button onClick={() => setShowAddModal(true)} className="w-full py-2 bg-blue-600 text-white rounded-lg flex items-center justify-center gap-2"><Plus size={16}/> 增加门店计划</button>
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
              {unscheduledStores.length === 0 ? <div className="text-center py-8 text-gray-400">所有未导入门店任务已安排！</div> : unscheduledStores.map(store => {
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
                          <span className={`${store.plannedCount >= store.monthlyFrequency ? 'text-green-600' : 'text-blue-600'}`}>
                            进度: {store.plannedCount}/{store.monthlyFrequency}
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
                disabled={selectedStoreIds.length === 0}
                className="w-full bg-blue-600 text-white py-3 rounded-lg text-base font-bold shadow-md active:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {selectedStoreIds.length > 0 ? `确认添加 ${selectedStoreIds.length} 个门店` : '请选择门店'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
