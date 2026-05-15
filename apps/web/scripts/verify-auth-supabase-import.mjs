import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

const files = {
  browserClient: "lib/supabase.ts",
  middleware: "middleware.ts",
  authForm: "components/auth-form.tsx",
  sessionProvider: "components/session-provider.tsx",
  dashboard: "components/dashboard.tsx",
  importParser: "lib/import-parser.ts",
  supabaseConfig: "lib/supabase-config.ts",
};

const source = Object.fromEntries(
  Object.entries(files).map(([key, relativePath]) => [
    key,
    readFileSync(join(root, relativePath), "utf8"),
  ]),
);

const checks = [
  {
    name: "browser Supabase client reads NEXT_PUBLIC_SUPABASE_URL",
    pass:
      source.browserClient.includes("getSupabasePublicConfig") &&
      source.supabaseConfig.includes("process.env.NEXT_PUBLIC_SUPABASE_URL"),
  },
  {
    name: "browser Supabase client reads NEXT_PUBLIC_SUPABASE_ANON_KEY",
    pass:
      source.browserClient.includes("getSupabasePublicConfig") &&
      source.supabaseConfig.includes("process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY"),
  },
  {
    name: "middleware reads NEXT_PUBLIC_SUPABASE_URL",
    pass: source.supabaseConfig.includes("process.env.NEXT_PUBLIC_SUPABASE_URL"),
  },
  {
    name: "middleware reads NEXT_PUBLIC_SUPABASE_ANON_KEY",
    pass: source.supabaseConfig.includes("process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY"),
  },
  {
    name: "middleware validates the authenticated user with getUser",
    pass: source.middleware.includes("supabase.auth.getUser()"),
  },
  {
    name: "middleware redirects unauthenticated private routes to login",
    pass: source.middleware.includes("NextResponse.redirect") && source.middleware.includes('pathname = "/login"'),
  },
  {
    name: "Supabase client validates URL and anon key before client creation",
    pass:
      source.browserClient.includes("getSupabasePublicConfig") &&
      source.middleware.includes("getSupabasePublicConfig") &&
      source.supabaseConfig.includes("new URL(url)") &&
      source.supabaseConfig.includes("anonKey.split"),
  },
  {
    name: "session bootstrap uses getUser",
    pass: source.sessionProvider.includes("supabase.auth.getUser()"),
  },
  {
    name: "session state subscribes with onAuthStateChange",
    pass: source.sessionProvider.includes("supabase.auth.onAuthStateChange("),
  },
  {
    name: "session sign out calls Supabase signOut",
    pass: source.sessionProvider.includes(".auth.signOut()"),
  },
  {
    name: "password login uses Supabase signIn",
    pass: /supabase\.auth\.signIn(?:WithPassword)?\s*\(/.test(source.authForm),
  },
  {
    name: "signup uses Supabase signUp",
    pass: source.authForm.includes("supabase.auth.signUp("),
  },
  {
    name: "upload input accepts CSV and PDF",
    pass: /accept=["'][^"']*\.csv[^"']*\.pdf[^"']*["']/.test(source.dashboard),
  },
  {
    name: "upload input rejects TXT",
    pass: !/accept=["'][^"']*\.txt[^"']*["']/.test(source.dashboard),
  },
  {
    name: "import parser accepts CSV",
    pass: source.importParser.includes('"csv"'),
  },
  {
    name: "import parser accepts PDF",
    pass: source.importParser.includes('"pdf"'),
  },
  {
    name: "import parser rejects TXT extension",
    pass: !source.importParser.includes('"txt"') && !source.importParser.includes(".txt"),
  },
  {
    name: "import parser rejects disguised or corrupted CSV content",
    pass: source.importParser.includes("looksLikeCorruptedOrDisguisedCsv") && source.importParser.includes("REJECTED_FILE_SIGNATURES"),
  },
  {
    name: "upload errors do not expose implementation details",
    pass: !source.dashboard.includes("error.message") && !source.importParser.includes("stack"),
  },
];

const failures = checks.filter((check) => !check.pass);

for (const check of checks) {
  console.log(`${check.pass ? "PASS" : "FAIL"} ${check.name}`);
}

if (failures.length > 0) {
  console.error(`\n${failures.length} verification check(s) failed.`);
  process.exitCode = 1;
}
