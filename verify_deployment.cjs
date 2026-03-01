const axios = require('axios');

async function verifyDeployment() {
  const baseURL = 'http://localhost:3000';
  
  try {
    console.log('Verifying /workspace (Landing Page)...');
    const landing = await axios.get(`${baseURL}/workspace`);
    if (landing.data.includes('ZeoSite Workspace') && landing.data.includes('个人空间')) {
      console.log('✅ Landing Page served correctly.');
    } else {
      console.error('❌ Landing Page content mismatch.');
    }

    console.log('Verifying /workspace/schedule (Service Mate)...');
    // Note: This might return index.html which is a small file referencing assets
    const app = await axios.get(`${baseURL}/workspace/schedule/`);
    if (app.data.includes('<!doctype html>') && app.data.includes('/workspace/schedule/assets/')) {
      console.log('✅ Service Mate served correctly with correct base path.');
    } else {
      console.error('❌ Service Mate content mismatch or base path incorrect.');
      console.log('Content preview:', app.data.substring(0, 200));
    }

    console.log('Verifying Redirect / -> /workspace ...');
    const redirect = await axios.get(`${baseURL}/`, { maxRedirects: 0, validateStatus: s => s === 302 });
    if (redirect.status === 302 && redirect.headers.location === '/workspace') {
      console.log('✅ Root redirect works.');
    } else {
      // Axios follows redirects by default unless configured.
      // Let's try allowing redirects and check final URL if axios supports that property, 
      // but simpler to just check if it lands on workspace content.
      const followed = await axios.get(`${baseURL}/`);
      if (followed.request.path === '/workspace' || followed.data.includes('ZeoSite Workspace')) {
        console.log('✅ Root redirect eventually lands on workspace.');
      }
    }

  } catch (e) {
    console.error('Verify failed:', e.message);
    if (e.response) {
        console.error('Status:', e.response.status);
        console.error('Headers:', e.response.headers);
    }
  }
}

verifyDeployment();
