import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

import ts from "typescript";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

function readSource(relativePath) {
  return readFileSync(join(root, relativePath), "utf8");
}

function loadTsModule(relativePath, mocks = {}, globals = {}) {
  const source = readSource(relativePath);
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      esModuleInterop: true,
      jsx: ts.JsxEmit.React,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;

  const module = { exports: {} };
  const context = vm.createContext({
    Blob,
    File,
    TextDecoder,
    URL,
    console,
    exports: module.exports,
    module,
    process,
    ...globals,
    require(specifier) {
      if (specifier in mocks) {
        return mocks[specifier];
      }
      throw new Error(`Unexpected test import: ${specifier}`);
    },
  });

  vm.runInContext(compiled, context, { filename: relativePath });
  return module.exports;
}

function makeFile(parts, name, type = "") {
  return new File(parts, name, { type });
}

function assertSafeUserMessage(message) {
  assert.equal(typeof message, "string");
  assert.ok(message.length > 0);
  assert.doesNotMatch(message, /(?:Error|TypeError|ReferenceError|stack|at\s+\w+\s*\(|\/home\/|node_modules)/);
  assert.doesNotMatch(message, /<script|select\s+\*|token|secret|anon[_-]?key/i);
}

test("upload parser accepts valid CSV and normalizes imported assets", async () => {
  const { parseBrokerageFile } = loadTsModule("lib/import-parser.ts");
  const file = makeFile(
    ["ticker,quantity,average_price,asset_type\npetr4,10,32.5,stock\n"],
    "wallet.csv",
    "text/csv",
  );

  const result = await parseBrokerageFile(file);

  assert.equal(result.ok, true);
  assert.equal(result.assets.length, 1);
  assert.equal(result.assets[0].ticker, "PETR4");
  assert.equal(result.assets[0].quantity, 10);
  assert.equal(result.assets[0].average_price, 32.5);
  assert.equal(result.assets[0].asset_type, "stock");
});

test("upload parser allows only CSV/PDF extensions and safe MIME types", async () => {
  const { parseBrokerageFile } = loadTsModule("lib/import-parser.ts");
  const rejectedFiles = [
    makeFile(["ticker,quantity,average_price\nPETR4,1,10\n"], "wallet.txt", "text/plain"),
    makeFile(["{}"], "wallet.json", "application/json"),
    makeFile(["<html></html>"], "wallet.html", "text/html"),
    makeFile(["fake image"], "wallet.png", "image/png"),
    makeFile(["spreadsheet"], "wallet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    makeFile(["ticker,quantity,average_price\nPETR4,1,10\n"], "wallet.csv", "application/json"),
    makeFile(["%PDF-1.7"], "wallet.pdf", "text/plain"),
  ];

  for (const file of rejectedFiles) {
    const result = await parseBrokerageFile(file);
    assert.equal(result.ok, false, `${file.name} should be rejected`);
    assert.equal(result.message, "Formato invalido. Envie apenas arquivo CSV ou PDF.");
    assertSafeUserMessage(result.message);
  }
});

test("upload parser accepts PDF as a supported format but rejects invalid PDF content safely", async () => {
  const { parseBrokerageFile } = loadTsModule("lib/import-parser.ts");

  const invalidPdf = await parseBrokerageFile(makeFile(["not a pdf"], "statement.pdf", "application/pdf"));
  const supportedPdf = await parseBrokerageFile(makeFile(["%PDF-1.7\n"], "statement.PDF", "application/pdf"));

  assert.equal(invalidPdf.ok, false);
  assert.equal(invalidPdf.message, "Arquivo invalido ou corrompido. Verifique o arquivo e tente novamente.");
  assertSafeUserMessage(invalidPdf.message);

  assert.equal(supportedPdf.ok, false);
  assert.equal(
    supportedPdf.message,
    "Nao foi possivel importar os ativos deste PDF. Envie um CSV com ticker, quantity e average_price.",
  );
  assertSafeUserMessage(supportedPdf.message);
});

test("upload parser exposes safe user messages for parse failures", async () => {
  const { parseBrokerageFile } = loadTsModule("lib/import-parser.ts");
  const cases = [
    makeFile([], "empty.csv", "text/csv"),
    makeFile(["ticker,quantity\nPETR4,1\n"], "missing-column.csv", "text/csv"),
    makeFile(["ticker,quantity,average_price\nPETR4,-1,10\n"], "invalid-number.csv", "text/csv"),
    {
      name: "broken.csv",
      type: "text/csv",
      size: 10,
      arrayBuffer: async () => {
        throw new Error("Sensitive stack with token=abc123");
      },
    },
  ];

  for (const file of cases) {
    const result = await parseBrokerageFile(file);
    assert.equal(result.ok, false, `${file.name} should fail safely`);
    assertSafeUserMessage(result.message);
  }
});

test("upload input advertises only CSV and PDF formats", () => {
  const dashboard = readSource("components/dashboard.tsx");

  assert.match(dashboard, /type="file"/);
  assert.match(dashboard, /accept="\.csv,\.pdf,text\/csv,application\/pdf"/);
  assert.doesNotMatch(dashboard, /accept="[^"]*(?:\.txt|text\/plain|\.xlsx|application\/json)[^"]*"/);
});

test("Supabase public config validates required environment shape", () => {
  const { getSupabasePublicConfig, isValidSupabaseConfig } = loadTsModule("lib/supabase-config.ts");
  const originalUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const originalAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const originalPublishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  try {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    assert.equal(getSupabasePublicConfig(), null);

    assert.equal(isValidSupabaseConfig(undefined, "header.payload.signature"), false);
    assert.equal(isValidSupabaseConfig("https://example.supabase.co", undefined), false);
    assert.equal(isValidSupabaseConfig("ftp://example.supabase.co", "header.payload.signature"), false);
    assert.equal(isValidSupabaseConfig("https://example.supabase.co", "short"), false);
    assert.equal(isValidSupabaseConfig("https://example.supabase.co", "not-a-jwt-shaped-key"), false);
    assert.equal(isValidSupabaseConfig("https://example.supabase.co", "header.payload.signature"), true);
    assert.equal(isValidSupabaseConfig("https://example.supabase.co", "sb_publishable_12345678901234567890"), true);
    assert.equal(isValidSupabaseConfig("http://localhost:54321", "header.payload.signature"), true);

    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_12345678901234567890";
    const config = getSupabasePublicConfig();
    assert.equal(config.url, "https://example.supabase.co");
    assert.equal(config.anonKey, "sb_publishable_12345678901234567890");
  } finally {
    if (originalUrl === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_URL = originalUrl;
    }
    if (originalAnonKey === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = originalAnonKey;
    }
    if (originalPublishableKey === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = originalPublishableKey;
    }
  }
});

test("Supabase browser client validates environment before creating a client", () => {
  const calls = [];
  const { createSupabaseBrowserClient } = loadTsModule("lib/supabase.ts", {
    "@supabase/ssr": {
      createBrowserClient(url, anonKey) {
        calls.push({ url, anonKey });
        return { url, anonKey };
      },
    },
    "@/lib/supabase-config": {
      getSupabasePublicConfig() {
        const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
        const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
        return url && anonKey ? { url, anonKey } : null;
      },
    },
  });
  const originalUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const originalAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  try {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    assert.equal(createSupabaseBrowserClient(), null);
    assert.deepEqual(calls, []);

    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "header.payload.signature";
    const client = createSupabaseBrowserClient();
    assert.equal(client.url, "https://example.supabase.co");
    assert.equal(client.anonKey, "header.payload.signature");
    assert.deepEqual(calls, [
      {
        url: "https://example.supabase.co",
        anonKey: "header.payload.signature",
      },
    ]);
  } finally {
    if (originalUrl === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_URL = originalUrl;
    }
    if (originalAnonKey === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = originalAnonKey;
    }
  }
});

test("middleware skips Supabase auth when environment is incomplete", async () => {
  let createServerClientCalls = 0;
  let nextCalls = 0;
  const { middleware } = loadTsModule("middleware.ts", {
    "@supabase/ssr": {
      createServerClient() {
        createServerClientCalls += 1;
        throw new Error("createServerClient should not be called without env");
      },
    },
    "@/lib/supabase-config": {
      getSupabasePublicConfig() {
        return null;
      },
    },
    "next/server": {
      NextResponse: {
        next(requestOptions) {
          nextCalls += 1;
          return { cookies: { set() {} }, requestOptions };
        },
      },
    },
  });
  const originalUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const originalAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  try {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    const response = await middleware({ cookies: { getAll: () => [], set() {} } });

    assert.equal(nextCalls, 1);
    assert.equal(createServerClientCalls, 0);
    assert.ok(response);
  } finally {
    if (originalUrl === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_URL = originalUrl;
    }
    if (originalAnonKey === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = originalAnonKey;
    }
  }
});

test("middleware initializes Supabase auth and validates the user when env is configured", async () => {
  const cookieWrites = [];
  const requestCookieWrites = [];
  let getUserCalls = 0;
  let observedCookieHandlers;
  const { middleware, config } = loadTsModule("middleware.ts", {
    "@supabase/ssr": {
      createServerClient(url, anonKey, options) {
        observedCookieHandlers = options.cookies;
        assert.equal(url, "https://example.supabase.co");
        assert.equal(anonKey, "header.payload.signature");
        return {
          auth: {
            async getUser() {
              getUserCalls += 1;
              options.cookies.setAll([
                {
                  name: "sb-session",
                  value: "refreshed",
                  options: { httpOnly: true, sameSite: "lax" },
                },
              ]);
              return { data: { user: { id: "user-1" } }, error: null };
            },
          },
        };
      },
    },
    "@/lib/supabase-config": {
      getSupabasePublicConfig() {
        return {
          url: process.env.NEXT_PUBLIC_SUPABASE_URL,
          anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
        };
      },
    },
    "next/server": {
      NextResponse: {
        next(requestOptions) {
          return {
            cookies: {
              set(name, value, options) {
                cookieWrites.push({ name, value, options });
              },
            },
            requestOptions,
          };
        },
        redirect(url) {
          return { redirectedTo: url };
        },
      },
    },
  });
  const originalUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const originalAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  try {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "header.payload.signature";
    const request = {
      nextUrl: new URL("https://app.example.test/"),
      cookies: {
        getAll: () => [{ name: "sb-session", value: "old" }],
        set(name, value) {
          requestCookieWrites.push({ name, value });
        },
      },
    };

    const response = await middleware(request);

    assert.equal(getUserCalls, 1);
    assert.deepEqual(observedCookieHandlers.getAll(), [{ name: "sb-session", value: "old" }]);
    assert.deepEqual(requestCookieWrites, [{ name: "sb-session", value: "refreshed" }]);
    assert.deepEqual(cookieWrites, [
      {
        name: "sb-session",
        value: "refreshed",
        options: { httpOnly: true, sameSite: "lax" },
      },
    ]);
    assert.equal(response.redirectedTo, undefined);
    assert.equal(config.matcher.length, 1);
    assert.equal(config.matcher[0], "/((?!_next/static|_next/image|favicon.ico).*)");
  } finally {
    if (originalUrl === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_URL = originalUrl;
    }
    if (originalAnonKey === undefined) {
      delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    } else {
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = originalAnonKey;
    }
  }
});

test("auth UI and session bootstrap use safe auth paths and env validation messages", () => {
  const authForm = readSource("components/auth-form.tsx");
  const passwordChangeForm = readSource("components/password-change-form.tsx");
  const sessionProvider = readSource("components/session-provider.tsx");
  const apiSource = readSource("lib/api.ts");
  const envExample = readSource(".env.example");
  const typesSource = readSource("types/analysis.ts");

  assert.match(authForm, /createSupabaseBrowserClient\(\)/);
  assert.match(authForm, /Autenticacao indisponivel no momento\./);
  assert.match(authForm, /getSafeAuthErrorMessage\(response\.error\.message\)/);
  assert.match(authForm, /getSafeAuthErrorMessage\(googleError\.message\)/);
  assert.match(authForm, /signInWithPassword\(\{ email, password \}\)/);
  assert.match(authForm, /signUp\(\{/);
  assert.match(authForm, /signInWithOAuth\(\{/);
  assert.match(authForm, /MIN_PASSWORD_LENGTH = 8/);
  assert.match(authForm, /isPasswordStrongEnough\(password\)/);
  assert.match(authForm, /resetPasswordForEmail\(normalizedEmail/);
  assert.match(authForm, /redirectTo: `\$\{window\.location\.origin\}\/auth\/callback\?next=\/alterar-senha`/);
  assert.match(passwordChangeForm, /MIN_PASSWORD_LENGTH = 8/);
  assert.match(passwordChangeForm, /hasPasswordIdentity\(user\)/);
  assert.match(passwordChangeForm, /supabase\.auth\.updateUser\(\{ password \}\)/);

  assert.match(sessionProvider, /supabase\.auth\.getUser\(\)/);
  assert.match(sessionProvider, /supabase\.auth\.onAuthStateChange\(/);
  assert.match(sessionProvider, /supabase\?\.auth\.signOut\(\)/);
  assert.match(apiSource, /Authorization: `Bearer \$\{accessToken\}`/);
  assert.doesNotMatch(typesSource, /export type AnalysisRequest = \{[^}]*user_id/s);

  assert.match(envExample, /^NEXT_PUBLIC_SUPABASE_URL=/m);
  assert.match(envExample, /^NEXT_PUBLIC_SUPABASE_ANON_KEY=/m);
  assert.match(envExample, /^NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=/m);
});

test("API client attaches the Supabase Bearer token when a session exists", async () => {
  const fetchCalls = [];
  const { createAnalysis } = loadTsModule(
    "lib/api.ts",
    {
      "@/lib/supabase": {
        createSupabaseBrowserClient() {
          return {
            auth: {
              async getSession() {
                return { data: { session: { access_token: "access-token-123" } } };
              },
            },
          };
        },
      },
    },
    {
      fetch: async (url, init) => {
        fetchCalls.push({ url, init });
        return {
          ok: true,
          async json() {
            return { job_id: "job-123" };
          },
        };
      },
    },
  );

  const response = await createAnalysis({
    assets: [{ ticker: "PETR4", quantity: 10, average_price: 32.5 }],
    risk_profile: "moderate",
    monthly_contribution: 1000,
  });

  assert.deepEqual(response, { job_id: "job-123" });
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].url, "http://localhost:8000/api/v1/analysis");
  assert.equal(fetchCalls[0].init.method, "POST");
  assert.equal(fetchCalls[0].init.headers.Authorization, "Bearer access-token-123");
  assert.equal(fetchCalls[0].init.headers["Content-Type"], "application/json");
});

test("API client omits Authorization when there is no active Supabase session", async () => {
  const fetchCalls = [];
  const { getAnalysisStatus } = loadTsModule(
    "lib/api.ts",
    {
      "@/lib/supabase": {
        createSupabaseBrowserClient() {
          return {
            auth: {
              async getSession() {
                return { data: { session: null } };
              },
            },
          };
        },
      },
    },
    {
      fetch: async (url, init) => {
        fetchCalls.push({ url, init });
        return {
          ok: true,
          async json() {
            return {
              status: "pending",
              current_step: "queued",
              progress_percentage: 0,
              attempt_count: 0,
              max_attempts: 1,
              retry_backoff_seconds: null,
              next_retry_at: null,
              error_message: null,
            };
          },
        };
      },
    },
  );

  await getAnalysisStatus("job-123");

  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].url, "http://localhost:8000/api/v1/analysis/status/job-123");
  assert.equal(fetchCalls[0].init.headers.Authorization, undefined);
});
