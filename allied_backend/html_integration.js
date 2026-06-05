/*
 ╔══════════════════════════════════════════════════════╗
 ║  ALLIED INDUSTRIES – BACKEND INTEGRATION SNIPPET     ║
 ║                                                      ║
 ║  Paste this <script> block into your HTML file,      ║
 ║  replacing the existing showToast() calls in the     ║
 ║  two form submit buttons.                            ║
 ╚══════════════════════════════════════════════════════╝

HOW TO USE
──────────
1. Find the Contact form submit button in your HTML (Search: "Send Enquiry →")
   Replace its onclick with: onclick="submitEnquiry()"

2. Find the Careers form submit button (Search: "Submit Application")
   Replace its onclick with: onclick="submitApplication()"

3. Paste the entire <script> block below just before </body>
   (or merge it into the existing <script> tag)

──────────────────────────────────────────────────────── */

// Change this to your server URL when deployed
// e.g. "https://www.alliedindustries.in"  or  "http://127.0.0.1:5000"
const BACKEND_URL = "http://127.0.0.1:5000";

/* ── CONTACT FORM ── */
async function submitEnquiry() {
  const form = document.querySelector('#page-contact .c-form');
  const inputs = form.querySelectorAll('input, select, textarea');
  const btn    = form.querySelector('button[onclick="submitEnquiry()"]');

  // Collect values
  const data = {
    name:    form.querySelector('input[placeholder="Full name"]')?.value?.trim()       || "",
    email:   form.querySelector('input[type="email"]')?.value?.trim()                  || "",
    phone:   form.querySelector('input[type="tel"]')?.value?.trim()                    || "",
    company: form.querySelector('input[placeholder="Your company"]')?.value?.trim()    || "",
    product: form.querySelector('select')?.value                                       || "",
    message: form.querySelector('textarea')?.value?.trim()                             || "",
  };

  if (!data.name || !data.email) {
    showToast("⚠️ Please fill in your name and email.");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Sending…";

  try {
    const res  = await fetch(`${BACKEND_URL}/api/enquiry`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(data),
    });
    const json = await res.json();

    if (json.ok) {
      showToast("✅ " + json.message);
      // Clear form
      inputs.forEach(el => { if (el.tagName !== "SELECT") el.value = ""; });
    } else {
      showToast("❌ " + (json.error || "Something went wrong. Please try again."));
    }
  } catch (err) {
    showToast("❌ Could not reach server. Please call us directly.");
  } finally {
    btn.disabled = false;
    btn.textContent = "Send Enquiry →";
  }
}


/* ── CAREER FORM ── */
async function submitApplication() {
  const form = document.querySelector('#page-careers .c-form-area');
  const btn  = form.querySelector('button[onclick="submitApplication()"]');

  const nameParts = (() => {
    const first = form.querySelector('input[placeholder="Rahul"]')?.value?.trim() || "";
    const last  = form.querySelector('input[placeholder="Sharma"]')?.value?.trim() || "";
    return { first, last };
  })();

  const data = {
    first_name: nameParts.first,
    last_name:  nameParts.last,
    email:      form.querySelector('input[type="email"]')?.value?.trim()   || "",
    phone:      form.querySelector('input[type="tel"]')?.value?.trim()     || "",
    position:   form.querySelector('select')?.value                        || "",
    cv_text:    form.querySelector('textarea')?.value?.trim()              || "",
  };

  if (!data.first_name || !data.email || !data.position) {
    showToast("⚠️ Please fill in your name, email and position.");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Submitting…";

  try {
    const res  = await fetch(`${BACKEND_URL}/api/application`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(data),
    });
    const json = await res.json();

    if (json.ok) {
      showToast("✅ " + json.message);
      form.querySelectorAll('input, textarea').forEach(el => el.value = "");
    } else {
      showToast("❌ " + (json.error || "Something went wrong. Please try again."));
    }
  } catch (err) {
    showToast("❌ Could not reach server. Please email us directly.");
  } finally {
    btn.disabled = false;
    btn.textContent = "Submit Application";
  }
}
