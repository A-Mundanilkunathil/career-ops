#!/usr/bin/env node
/**
 * apply-helper.mjs — opens an apply URL in a visible browser and pre-fills
 * standard fields + uploads the matching resume PDF. Stops before Submit.
 *
 * Usage:
 *   node dashboard-web/apply-helper.mjs <APPLY_URL> <RESUME_PDF_PATH>
 *
 * Detects ATS (Ashby / Greenhouse / Lever) and applies the right field map.
 * Browser stays open after pre-fill so the user can review + submit.
 */
import { chromium } from "playwright";
import { resolve } from "path";
import { existsSync } from "fs";

const PROFILE = {
  firstName: "Aaron",
  lastName: "Mundanilkunathil",
  fullName: "Aaron Mundanilkunathil",
  email: "aaron.mundanilkunathil@gmail.com",
  phone: "(408) 858-6197",
  phoneDigits: "4088586197",
  location: "San Jose, CA",
  linkedin: "https://linkedin.com/in/aaron-mundanilkunathil",
  github: "https://github.com/A-Mundanilkunathil",
  portfolio: "https://github.com/A-Mundanilkunathil",
  school: "San Jose State University",
  degree: "Bachelor of Science",
  major: "Computer Science",
  gradMonth: "May",
  gradYear: "2027",
  workAuth: "Yes",
  sponsorship: "No",
};

function detectAts(url) {
  if (url.includes("ashbyhq.com")) return "ashby";
  if (url.includes("greenhouse.io")) return "greenhouse";
  if (url.includes("lever.co")) return "lever";
  return "unknown";
}

async function tryFill(page, selector, value) {
  try {
    const el = await page.$(selector);
    if (el) {
      await el.fill(value);
      console.log(`  ✓ filled ${selector}`);
      return true;
    }
  } catch (e) { /* ignore */ }
  return false;
}

async function tryClick(page, selector) {
  try {
    const el = await page.$(selector);
    if (el) {
      await el.click();
      console.log(`  ✓ clicked ${selector}`);
      return true;
    }
  } catch (e) { /* ignore */ }
  return false;
}

async function tryUpload(page, selector, filePath) {
  try {
    const el = await page.$(selector);
    if (el) {
      await el.setInputFiles(filePath);
      console.log(`  ✓ uploaded ${filePath} to ${selector}`);
      return true;
    }
  } catch (e) {
    console.log(`  ✗ upload failed ${selector}: ${e.message}`);
  }
  return false;
}

async function fillAshby(page, resumePath) {
  console.log("Detected: Ashby");
  // Wait for the form to render
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});

  // Click "Apply" button if on listing page (some Ashby links go to listing, not form)
  await tryClick(page, 'a[href*="/application"]:has-text("Apply")');
  await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});

  // Ashby system fields
  await tryFill(page, 'input[id="_systemfield_name"]', PROFILE.fullName);
  await tryFill(page, 'input[name="name"]', PROFILE.fullName);
  await tryFill(page, 'input[id="_systemfield_email"]', PROFILE.email);
  await tryFill(page, 'input[name="email"]', PROFILE.email);
  await tryFill(page, 'input[id="_systemfield_phone"]', PROFILE.phone);
  await tryFill(page, 'input[name="phone"]', PROFILE.phone);
  await tryFill(page, 'input[id="_systemfield_location"]', PROFILE.location);
  await tryFill(page, 'input[name="location"]', PROFILE.location);
  await tryFill(page, 'input[id="_systemfield_resume"]', resumePath); // sometimes file input

  // Resume upload — Ashby uses input[type=file]
  const fileInputs = await page.$$('input[type="file"]');
  if (fileInputs.length > 0) {
    await fileInputs[0].setInputFiles(resumePath);
    console.log(`  ✓ uploaded resume via input[type=file] (count: ${fileInputs.length})`);
  }

  // LinkedIn / portfolio fields
  await tryFill(page, 'input[name*="linkedin" i]', PROFILE.linkedin);
  await tryFill(page, 'input[name*="github" i]', PROFILE.github);
  await tryFill(page, 'input[name*="portfolio" i]', PROFILE.portfolio);
  await tryFill(page, 'input[name*="website" i]', PROFILE.portfolio);
}

async function fillGreenhouse(page, resumePath) {
  console.log("Detected: Greenhouse");
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});

  await tryFill(page, '#first_name', PROFILE.firstName);
  await tryFill(page, '#last_name', PROFILE.lastName);
  await tryFill(page, '#email', PROFILE.email);
  await tryFill(page, '#phone', PROFILE.phone);
  await tryFill(page, 'input[id*="resume_url"]', "");

  // Greenhouse resume upload
  const resumeInputs = await page.$$('input[type="file"]');
  if (resumeInputs.length > 0) {
    await resumeInputs[0].setInputFiles(resumePath);
    console.log(`  ✓ uploaded resume`);
  }

  // Custom fields
  await tryFill(page, 'input[name*="linkedin" i]', PROFILE.linkedin);
  await tryFill(page, 'input[name*="github" i]', PROFILE.github);
  await tryFill(page, 'input[name*="school" i]', PROFILE.school);
}

async function fillLever(page, resumePath) {
  console.log("Detected: Lever");
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});

  // Lever forms have various field structures
  await tryFill(page, 'input[name="name"]', PROFILE.fullName);
  await tryFill(page, 'input[name="email"]', PROFILE.email);
  await tryFill(page, 'input[name="phone"]', PROFILE.phone);
  await tryFill(page, 'input[name="org"]', PROFILE.school);
  await tryFill(page, 'input[name="urls[LinkedIn]"]', PROFILE.linkedin);
  await tryFill(page, 'input[name="urls[GitHub]"]', PROFILE.github);
  await tryFill(page, 'input[name="urls[Portfolio]"]', PROFILE.portfolio);
  await tryFill(page, 'input[placeholder*="Location" i]', PROFILE.location);

  const fileInputs = await page.$$('input[type="file"]');
  if (fileInputs.length > 0) {
    await fileInputs[0].setInputFiles(resumePath);
    console.log(`  ✓ uploaded resume`);
  }
}

async function main() {
  const [, , urlArg, pdfArg] = process.argv;
  if (!urlArg || !pdfArg) {
    console.error("Usage: node apply-helper.mjs <APPLY_URL> <RESUME_PDF_PATH>");
    process.exit(1);
  }

  const resumePath = resolve(pdfArg);
  if (!existsSync(resumePath)) {
    console.error(`Resume not found: ${resumePath}`);
    process.exit(1);
  }

  const ats = detectAts(urlArg);
  console.log(`Opening ${urlArg}`);
  console.log(`Resume:  ${resumePath}`);
  console.log(`ATS:     ${ats}`);

  const browser = await chromium.launch({
    headless: false,
    args: ["--no-default-browser-check"],
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(urlArg, { waitUntil: "domcontentloaded", timeout: 60000 });

  if (ats === "ashby") await fillAshby(page, resumePath);
  else if (ats === "greenhouse") await fillGreenhouse(page, resumePath);
  else if (ats === "lever") await fillLever(page, resumePath);
  else {
    console.log("Unknown ATS — page is open but not auto-filled. Fill it manually.");
  }

  console.log("\n──────────────────────────────────────────────");
  console.log("Browser is open. Review the form, complete any");
  console.log("essay/optional questions, and click SUBMIT yourself.");
  console.log("Then close the browser window manually when done.");
  console.log("──────────────────────────────────────────────");

  // Keep the script alive until browser is closed
  await new Promise((resolve) => browser.on("disconnected", resolve));
}

main().catch((err) => {
  console.error("Error:", err);
  process.exit(1);
});
