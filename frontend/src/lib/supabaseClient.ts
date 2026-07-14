import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl) {
    throw new Error("CRITICAL BUILD ERROR: NEXT_PUBLIC_SUPABASE_URL is not set. This must be provided during build time.");
}

if (!supabaseAnonKey) {
    throw new Error("CRITICAL BUILD ERROR: NEXT_PUBLIC_SUPABASE_ANON_KEY is not set. This must be provided during build time.");
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
