export type SupabasePublicConfig = {
  url: string;
  anonKey: string;
};

export function getSupabasePublicConfig(): SupabasePublicConfig | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey || !isValidSupabaseConfig(url, anonKey)) {
    return null;
  }

  return { url, anonKey };
}

export function isValidSupabaseConfig(url: string | undefined, anonKey: string | undefined) {
  if (!url || !anonKey) {
    return false;
  }

  try {
    const parsedUrl = new URL(url);
    const isAllowedProtocol = parsedUrl.protocol === "https:" || parsedUrl.hostname === "localhost";
    const hasHost = parsedUrl.hostname.length > 0;
    const hasLikelyAnonKey = anonKey.length > 20 && anonKey.split(".").length === 3;

    return isAllowedProtocol && hasHost && hasLikelyAnonKey;
  } catch {
    return false;
  }
}
