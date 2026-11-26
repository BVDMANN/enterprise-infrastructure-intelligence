import { appendFile, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const SEVERITIES = ["critical", "high", "moderate", "low", "info"];
const COUNT_FIELDS = ["total", ...SEVERITIES];

export function summarizeNpmAudit(rawOutput, exitCode) {
  const code = Number(exitCode);
  if (!Number.isInteger(code) || ![0, 1].includes(code)) {
    throw new Error("npm audit returned unexpected exit code " + exitCode);
  }

  let report;
  try {
    report = JSON.parse(rawOutput);
  } catch (error) {
    throw new Error("npm audit output was not valid JSON", { cause: error });
  }

  if (!report || typeof report !== "object" || Array.isArray(report)) {
    throw new Error("npm audit report must be a JSON object");
  }

  const counts = report.metadata?.vulnerabilities;
  if (!counts || typeof counts !== "object" || Array.isArray(counts)) {
    throw new Error("npm audit report is missing vulnerability metadata");
  }
  for (const field of COUNT_FIELDS) {
    if (!Number.isInteger(counts[field]) || counts[field] < 0) {
      throw new Error("npm audit vulnerability metadata has an invalid " + field + " count");
    }
  }

  const vulnerabilities = report.vulnerabilities ?? {};
  if (
    !vulnerabilities ||
    typeof vulnerabilities !== "object" ||
    Array.isArray(vulnerabilities)
  ) {
    throw new Error("npm audit report has an invalid vulnerabilities object");
  }

  const packages = Object.entries(vulnerabilities);
  for (const [name, finding] of packages) {
    if (!finding || typeof finding !== "object" || typeof finding.severity !== "string") {
      throw new Error("npm audit report has an invalid finding for package " + name);
    }
  }

  if (counts.total > 0 && packages.length === 0) {
    throw new Error("npm audit reports vulnerabilities but lists no affected packages");
  }
  if (code === 1 && counts.total === 0) {
    throw new Error("npm audit exited 1 but reported zero vulnerabilities");
  }

  const status = counts.total === 0 ? "CLEAN" : "FINDINGS (report-only)";
  const packageLines = packages.map(
    ([name, finding]) => "- " + name + ": " + finding.severity,
  );

  return [
    "### Node dependency audit — " + status,
    "npm audit exit code: " + code,
    "Total: " + counts.total + "; critical: " + counts.critical + "; high: " + counts.high + "; moderate: " + counts.moderate + "; low: " + counts.low + "; info: " + counts.info,
    ...(packageLines.length ? packageLines : ["No affected packages were reported."]),
    counts.total === 0
      ? "No known vulnerabilities were reported."
      : "Findings remain unresolved. The CI job is not evidence that this audit is clean.",
    "",
  ].join("\n");
}

async function main() {
  const [reportPath, exitCode] = process.argv.slice(2);
  if (!reportPath || exitCode === undefined) {
    throw new Error("Usage: node npm-audit-summary.mjs <report.json> <npm-exit-code>");
  }

  let summary;
  try {
    summary = summarizeNpmAudit(await readFile(reportPath, "utf8"), exitCode);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    summary = "### Node dependency audit — ERROR\n" + message + "\n";
    console.error(message);
    if (process.env.GITHUB_STEP_SUMMARY) {
      await appendFile(process.env.GITHUB_STEP_SUMMARY, summary + "\n");
    }
    process.exitCode = 2;
    return;
  }

  console.log(summary);
  if (process.env.GITHUB_STEP_SUMMARY) {
    await appendFile(process.env.GITHUB_STEP_SUMMARY, summary + "\n");
  }
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  await main();
}
