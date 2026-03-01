const API_BASE = 'http://localhost:3000/api';
let adminToken = '';
let userToken = '';

async function runTests() {
  console.log('🚀 Starting Auth System Tests...');

  try {
    // 1. 测试注册
    console.log('\n--- Test 1: User Registration ---');
    const regRes = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: 'testadmin',
        password: 'password123',
        email: 'admin@example.com',
        phone: '1234567890',
        role: 'admin'
      })
    });
    const regData = await regRes.json();
    console.log('Admin registration:', regRes.status === 200 ? '✅ Success' : '❌ Failed', regData);

    const regUserRes = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: 'testuser',
        password: 'password123',
        email: 'user@example.com',
        phone: '0987654321',
        role: 'user'
      })
    });
    console.log('User registration:', regUserRes.status === 200 ? '✅ Success' : '❌ Failed');

    // 2. 测试登录
    console.log('\n--- Test 2: User Login ---');
    const loginRes = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'testadmin', password: 'password123' })
    });
    const loginData = await loginRes.json();
    adminToken = loginData.token;
    console.log('Admin login:', adminToken ? '✅ Success (Token received)' : '❌ Failed');

    const loginUserRes = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'testuser', password: 'password123' })
    });
    const loginUserData = await loginUserRes.json();
    userToken = loginUserData.token;
    console.log('User login:', userToken ? '✅ Success (Token received)' : '❌ Failed');

    // 3. 测试受保护接口访问 (权限验证)
    console.log('\n--- Test 3: Protected Route Access ---');
    const storesRes = await fetch(`${API_BASE}/stores`, {
      headers: { 'Authorization': `Bearer ${adminToken}` }
    });
    console.log('Admin access to /stores:', storesRes.status === 200 ? '✅ Success' : '❌ Failed');

    const unauthorizedRes = await fetch(`${API_BASE}/stores`);
    console.log('Unauthorized access (no token):', unauthorizedRes.status === 401 ? '✅ Correctly Blocked' : '❌ Failed');

    // 4. 测试安全性 (SQL注入简单验证)
    console.log('\n--- Test 4: Security (SQL Injection) ---');
    const sqlInjectionRes = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: "' OR '1'='1", password: 'any' })
    });
    console.log('SQL Injection attempt:', sqlInjectionRes.status === 401 ? '✅ Correctly Blocked' : '❌ Vulnerable!');

    console.log('\n✨ All tests completed!');
    process.exit(0);
  } catch (error) {
    console.error('❌ Test execution failed:', error);
    process.exit(1);
  }
}

runTests();
