/* ==========================================================================
   HRzest - Modern Interactive Application Logic
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  initNavbar();
  initModal();
  initHeroScanner();
  initSandboxTabs();
  initPayrollCalculator();
  initLeaveWorkflow();
  initOrgVault();
  initContactForm();
  initFeedbackForm();
});

// ==========================================
// 1. Navbar Scroll Behavior & Mobile Menu
// ==========================================
function initNavbar() {
  const navbar = document.getElementById('navbar');
  const mobileNavToggle = document.getElementById('mobileNavToggle');
  const navLinks = document.querySelector('.nav-links');
  const navLinkItems = document.querySelectorAll('.nav-link');

  window.addEventListener('scroll', () => {
    if (window.scrollY > 30) {
      navbar?.classList.add('scrolled');
    } else {
      navbar?.classList.remove('scrolled');
    }

    // Scrollspy active section highlighting
    const sections = document.querySelectorAll('section[id]');
    const scrollY = window.pageYOffset;

    sections.forEach(current => {
      const sectionHeight = current.offsetHeight;
      const sectionTop = current.offsetTop - 120;
      const sectionId = current.getAttribute('id');

      if (scrollY > sectionTop && scrollY <= sectionTop + sectionHeight) {
        navLinkItems.forEach(item => {
          if (item.getAttribute('href') === `#${sectionId}`) {
            item.style.color = 'var(--accent-cyan)';
          } else {
            item.style.color = 'var(--text-muted)';
          }
        });
      }
    });
  });

  mobileNavToggle?.addEventListener('click', () => {
    if (!navLinks) return;
    const isVisible = navLinks.style.display === 'flex';
    navLinks.style.display = isVisible ? 'none' : 'flex';

    if (!isVisible) {
      navLinks.style.flexDirection = 'column';
      navLinks.style.position = 'absolute';
      navLinks.style.top = '80px';
      navLinks.style.left = '0';
      navLinks.style.right = '0';
      navLinks.style.background = 'var(--bg-secondary)';
      navLinks.style.padding = '1.5rem';
      navLinks.style.borderBottom = '1px solid var(--border-color)';
    }
  });
}

// ==========================================
// 2. Lead Registration Modal Handler
// ==========================================
function initModal() {
  const leadModal = document.getElementById('leadModal');
  const openModalBtns = document.querySelectorAll('.open-lead-modal-btn');
  const closeLeadModal = document.getElementById('closeLeadModal');
  const closeSuccessBtn = document.getElementById('closeSuccessBtn');
  const leadForm = document.getElementById('leadRegistrationForm');
  const modalSuccessMsg = document.getElementById('modalSuccessMsg');

  function openModal() {
    leadModal?.classList.add('open');
    if (leadForm) leadForm.style.display = 'block';
    if (modalSuccessMsg) modalSuccessMsg.style.display = 'none';
  }

  function closeModal() {
    leadModal?.classList.remove('open');
  }

  openModalBtns.forEach(btn => btn.addEventListener('click', (e) => {
    e.preventDefault();
    openModal();
  }));

  closeLeadModal?.addEventListener('click', closeModal);
  closeSuccessBtn?.addEventListener('click', closeModal);

  leadModal?.addEventListener('click', (e) => {
    if (e.target === leadModal) closeModal();
  });

  leadForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fullName = document.getElementById('fullName')?.value?.trim();
    const workEmail = document.getElementById('workEmail')?.value?.trim();
    const phoneNumber = document.getElementById('phoneNumber')?.value?.trim();
    const companyName = document.getElementById('companyName')?.value?.trim();
    const errorEl = document.getElementById('leadFormError');
    const submitBtn = leadForm.querySelector('.form-submit-btn');

    if (errorEl) errorEl.style.display = 'none';
    if (submitBtn) submitBtn.disabled = true;

    try {
      const resp = await fetch('/api/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: fullName, email: workEmail, phone: phoneNumber, company_name: companyName,
        }),
      });
      const result = await resp.json().catch(() => ({}));

      if (!resp.ok || !result.ok) {
        if (errorEl) {
          errorEl.textContent = result.msg || 'Could not submit right now. Please try again.';
          errorEl.style.display = 'block';
        }
        return;
      }

      const successUserName = document.getElementById('successUserName');
      const successCompName = document.getElementById('successCompName');
      if (successUserName) successUserName.textContent = fullName || 'Customer';
      if (successCompName) successCompName.textContent = companyName || 'your organization';

      leadForm.style.display = 'none';
      if (modalSuccessMsg) modalSuccessMsg.style.display = 'block';
      leadForm.reset();
    } catch (err) {
      if (errorEl) {
        errorEl.textContent = 'Network error. Please check your connection and try again.';
        errorEl.style.display = 'block';
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

// ==========================================
// 3. Hero Scanner Terminal Simulation
// ==========================================
function initHeroScanner() {
  const triggerScanBtn = document.getElementById('triggerScanBtn');
  const triggerPasskeyBtn = document.getElementById('triggerPasskeyBtn');
  const faceTargetBox = document.getElementById('faceTargetBox');
  const hudStatus = document.getElementById('hudStatus');
  const hudConfidence = document.getElementById('hudConfidence');
  const attendanceLogsBody = document.getElementById('attendanceLogsBody');
  const scannerAvatar = document.getElementById('scannerAvatar');

  const mockUsers = [
    { name: 'Elena Rostova', role: 'UX Specialist', initials: 'ER' },
    { name: 'David Kim', role: 'Backend Lead', initials: 'DK' },
    { name: 'Sarah Jenkins', role: 'Lead Architect', initials: 'SJ' }
  ];

  let isScanning = false;

  triggerScanBtn?.addEventListener('click', () => {
    if (isScanning || !faceTargetBox || !hudStatus || !hudConfidence) return;
    isScanning = true;

    const randomUser = mockUsers[Math.floor(Math.random() * mockUsers.length)];
    if (scannerAvatar) scannerAvatar.textContent = randomUser.initials;

    faceTargetBox.className = 'face-target-box scanning';
    hudStatus.textContent = 'Mapping 128d Face Mesh...';
    hudConfidence.textContent = 'Analyzing Liveness...';

    setTimeout(() => {
      hudStatus.textContent = 'Matching Database Vector...';
      hudConfidence.textContent = 'Confidence: 99.7%';
    }, 1000);

    setTimeout(() => {
      faceTargetBox.className = 'face-target-box success';
      hudStatus.textContent = `SUCCESS: ${randomUser.name}`;
      hudConfidence.textContent = 'GPS & Biometrics Verified!';

      appendAttendanceLog(randomUser.name, randomUser.role, 'AI Face ID', 'badge-face', 'ti-camera');

      setTimeout(() => {
        resetScannerHUD();
        isScanning = false;
      }, 2500);
    }, 2000);
  });

  triggerPasskeyBtn?.addEventListener('click', () => {
    if (isScanning || !faceTargetBox || !hudStatus || !hudConfidence) return;
    isScanning = true;

    faceTargetBox.className = 'face-target-box scanning';
    hudStatus.textContent = 'Waiting for TouchID / FIDO2 Passkey...';
    hudConfidence.textContent = 'Hardware Token Handshake';

    setTimeout(() => {
      faceTargetBox.className = 'face-target-box success';
      hudStatus.textContent = 'FIDO2 Passkey Authenticated!';
      hudConfidence.textContent = 'Zero-Knowledge Cryptographic Signature';

      appendAttendanceLog('Alex Rivera', 'Product Designer', 'TouchID Passkey', 'badge-passkey', 'ti-key');

      setTimeout(() => {
        resetScannerHUD();
        isScanning = false;
      }, 2500);
    }, 1500);
  });

  function resetScannerHUD() {
    if (faceTargetBox) faceTargetBox.className = 'face-target-box';
    if (hudStatus) hudStatus.textContent = 'Target Acquired';
    if (hudConfidence) hudConfidence.textContent = 'Confidence: 99.4%';
  }

  function appendAttendanceLog(name, role, methodLabel, badgeClass, iconClass) {
    if (!attendanceLogsBody) return;
    const timeNow = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const newRow = document.createElement('tr');
    newRow.innerHTML = `
      <td><strong>${name}</strong><br><small style="color:var(--text-subtle)">${role}</small></td>
      <td><span class="badge ${badgeClass}"><i class="ti ${iconClass}"></i> ${methodLabel}</span></td>
      <td>HQ Entrance (Verified)</td>
      <td>${timeNow}</td>
      <td><span style="color:var(--accent-emerald)"><i class="ti ti-circle-check"></i> Verified Just Now</span></td>
    `;
    attendanceLogsBody.insertBefore(newRow, attendanceLogsBody.firstChild);
  }
}

// ==========================================
// 4. Interactive Sandbox Tabs
// ==========================================
function initSandboxTabs() {
  const sandboxTabs = document.querySelectorAll('.sandbox-tab');
  const sandboxPanels = document.querySelectorAll('.sandbox-panel');
  const windowTitle = document.getElementById('windowTitle');

  const tabTitles = {
    'tab-attendance': 'HRzest Attendance & Biometric Monitoring Terminal',
    'tab-payroll': 'HRzest Automated Monthly Salary & Payslip Engine',
    'tab-leave': 'HRzest Smart Leave Requests & Shift Scheduler',
    'tab-org': 'HRzest Employee Document Vault & PDF Badge Generator'
  };

  sandboxTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetTab = tab.getAttribute('data-tab');

      sandboxTabs.forEach(t => t.classList.remove('active'));
      sandboxPanels.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const activePanel = document.getElementById(targetTab);
      if (activePanel) activePanel.classList.add('active');

      if (windowTitle && tabTitles[targetTab]) {
        windowTitle.textContent = tabTitles[targetTab];
      }
    });
  });
}

// ==========================================
// 5. Interactive Payroll Simulator
// ==========================================
function initPayrollCalculator() {
  const baseSalaryInput = document.getElementById('baseSalaryInput');
  const bonusInput = document.getElementById('bonusInput');
  const taxRateInput = document.getElementById('taxRateInput');

  const baseSalaryVal = document.getElementById('baseSalaryVal');
  const bonusVal = document.getElementById('bonusVal');
  const taxRateVal = document.getElementById('taxRateVal');

  const slipGross = document.getElementById('slipGross');
  const slipBonus = document.getElementById('slipBonus');
  const slipTax = document.getElementById('slipTax');
  const slipNet = document.getElementById('slipNet');

  function updatePayroll() {
    if (!baseSalaryInput || !bonusInput || !taxRateInput) return;
    const base = parseFloat(baseSalaryInput.value);
    const bonus = parseFloat(bonusInput.value);
    const taxRate = parseFloat(taxRateInput.value);

    const gross = base + bonus;
    const taxDeduction = gross * (taxRate / 100);
    const net = gross - taxDeduction;

    if (baseSalaryVal) baseSalaryVal.textContent = `₹${base.toLocaleString('en-IN')}`;
    if (bonusVal) bonusVal.textContent = `₹${bonus.toLocaleString('en-IN')}`;
    if (taxRateVal) taxRateVal.textContent = `${taxRate}%`;

    if (slipGross) slipGross.textContent = `₹${base.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    if (slipBonus) slipBonus.textContent = `₹${bonus.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    if (slipTax) slipTax.textContent = `-₹${taxDeduction.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    if (slipNet) slipNet.textContent = `₹${net.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  }

  [baseSalaryInput, bonusInput, taxRateInput].forEach(inp => {
    inp?.addEventListener('input', updatePayroll);
  });
  updatePayroll();
}

// ==========================================
// 6. Interactive Leave Approval Workflow
// ==========================================
function initLeaveWorkflow() {
  const approveLeaveBtn = document.getElementById('approveLeaveBtn');
  const leaveActionGroup = document.getElementById('leaveActionGroup');
  const leaveDaysCounter = document.getElementById('leaveDaysCounter');
  const leaveProgressBar = document.getElementById('leaveProgressBar');

  approveLeaveBtn?.addEventListener('click', () => {
    if (leaveActionGroup) {
      leaveActionGroup.innerHTML = `<span style="color:var(--accent-emerald); font-weight:700; font-size:0.85rem;"><i class="ti ti-circle-check"></i> Manager Approved</span>`;
    }
    if (leaveDaysCounter) {
      leaveDaysCounter.textContent = '12 / 20 Days Remaining';
    }
    if (leaveProgressBar) {
      leaveProgressBar.style.width = '60%';
    }
  });
}

// ==========================================
// 7. Interactive Org Vault Employee Selector
// ==========================================
function initOrgVault() {
  const orgUserBtns = document.querySelectorAll('.org-user-btn');
  const badgePhoto = document.getElementById('badgePhoto');
  const badgeName = document.getElementById('badgeName');
  const badgeRole = document.getElementById('badgeRole');
  const badgeId = document.getElementById('badgeId');

  const employees = {
    sarah: {
      name: 'Sarah Jenkins',
      role: 'Senior Software Architect',
      id: 'ID: HR-994821 | Dept: Engineering',
      initials: 'SJ'
    },
    alex: {
      name: 'Alex Rivera',
      role: 'Product Designer',
      id: 'ID: HR-884102 | Dept: Product UI/UX',
      initials: 'AR'
    },
    david: {
      name: 'David Kim',
      role: 'DevOps Lead',
      id: 'ID: HR-773919 | Dept: Cloud Infra',
      initials: 'DK'
    }
  };

  orgUserBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      orgUserBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const userKey = btn.getAttribute('data-user');
      const emp = employees[userKey];
      if (emp) {
        if (badgePhoto) badgePhoto.textContent = emp.initials;
        if (badgeName) badgeName.textContent = emp.name;
        if (badgeRole) badgeRole.textContent = emp.role;
        if (badgeId) badgeId.textContent = emp.id;
      }
    });
  });
}

// ==========================================
// 8. Contact Us Form Handler
// ==========================================
function initContactForm() {
  const contactForm = document.getElementById('contactForm');
  const contactSuccessMsg = document.getElementById('contactSuccessMsg');

  contactForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    if (contactForm) contactForm.style.display = 'none';
    if (contactSuccessMsg) contactSuccessMsg.style.display = 'flex';
  });
}

// ==========================================
// 9. Product Feedback Form & Star Rating Handler
// ==========================================
function initFeedbackForm() {
  const feedbackForm = document.getElementById('feedbackForm');
  const feedbackSuccessMsg = document.getElementById('feedbackSuccessMsg');

  // Category Pills Toggle
  const categoryPills = document.querySelectorAll('.category-pill');
  categoryPills.forEach(pill => {
    pill.addEventListener('click', () => {
      categoryPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
    });
  });

  // Star Rating Component
  const stars = document.querySelectorAll('#starRating .star');
  const ratingScoreText = document.getElementById('ratingScoreText');

  stars.forEach(star => {
    star.addEventListener('click', () => {
      const rating = parseInt(star.getAttribute('data-rating') || '5', 10);
      stars.forEach((s, idx) => {
        if (idx < rating) {
          s.classList.add('active');
        } else {
          s.classList.remove('active');
        }
      });
      if (ratingScoreText) ratingScoreText.textContent = `${rating}.0 / 5.0`;
    });
  });

  feedbackForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    if (feedbackForm) feedbackForm.style.display = 'none';
    if (feedbackSuccessMsg) feedbackSuccessMsg.style.display = 'flex';
  });
}
