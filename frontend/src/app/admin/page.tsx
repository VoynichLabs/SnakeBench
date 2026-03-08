import { createClient } from "@/lib/supabase/server";
import { isAllowedAdmin } from "@/lib/admin";
import AdminLoginButton from "@/components/admin/AdminLoginButton";
import AdminLogoutButton from "@/components/admin/AdminLogoutButton";
import MatchupPicker from "@/components/admin/MatchupPicker";

export default async function AdminPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Not logged in
  if (!user) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <h1 className="text-2xl font-bold text-white mb-8">Admin</h1>
        <AdminLoginButton />
      </div>
    );
  }

  const githubUsername =
    user.user_metadata?.user_name || user.user_metadata?.preferred_username;

  // Logged in but not authorized
  if (!isAllowedAdmin(githubUsername)) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <h1 className="text-2xl font-bold text-white mb-4">Access Denied</h1>
        <p className="text-zinc-400 mb-8">
          Your GitHub account ({githubUsername}) is not authorized.
        </p>
        <AdminLogoutButton />
      </div>
    );
  }

  // Authorized admin
  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-white">Admin</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-zinc-400">{githubUsername}</span>
          <AdminLogoutButton />
        </div>
      </div>
      <MatchupPicker />
    </div>
  );
}
