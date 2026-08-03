"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Eye, EyeOff, Loader2 } from "lucide-react";

import { AuthShell, AuthFooterLink } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { errorMessage } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import { useAuth } from "@/lib/auth/auth-context";
import Link from "next/link";

function GoogleIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" {...props}>
      <path
        fill="#4285F4"
        d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.47a5.54 5.54 0 0 1-2.4 3.63v3h3.88c2.27-2.09 3.57-5.17 3.57-8.82Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.95-2.91l-3.88-3c-1.08.73-2.46 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.27v3.11A12 12 0 0 0 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.28a7.2 7.2 0 0 1 0-4.56V6.61H1.27a12 12 0 0 0 0 10.78l4-3.11Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.76 0 3.34.6 4.58 1.79l3.44-3.44C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.27 6.61l4 3.11C6.22 6.86 8.87 4.75 12 4.75Z"
      />
    </svg>
  );
}

export default function SignupPage() {
  const router = useRouter();
  const { signup, status } = useAuth();
  const [showPassword, setShowPassword] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [googleLoading, setGoogleLoading] = React.useState(false);
  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [company, setCompany] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [agreedToTerms, setAgreedToTerms] = React.useState(false);

  /**
   * Bounce users who are *already* signed in when they land here.
   *
   * The `wasAlreadySignedIn` latch matters: without it this effect also fires
   * the instant `signup()` succeeds, racing — and beating — the explicit
   * `router.replace("/onboarding")` below, so new accounts skipped onboarding
   * entirely. Only a session that existed on mount triggers the bounce.
   */
  const wasAlreadySignedIn = React.useRef<boolean | null>(null);
  React.useEffect(() => {
    if (status === "loading") return;
    if (wasAlreadySignedIn.current === null) {
      wasAlreadySignedIn.current = status === "authenticated";
    }
    if (wasAlreadySignedIn.current && status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!fullName || !email || !company || !password) {
      toast.error("Please fill in all fields.");
      return;
    }
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }
    if (!agreedToTerms) {
      toast.error("Please accept the Terms of Service to continue.");
      return;
    }
    setLoading(true);
    try {
      // Signup creates the user, their organization, and a session in one call,
      // so the user is already authenticated when onboarding starts.
      await signup({ email, password, fullName, companyName: company });
      toast.success("Account created — let's get you set up.");
      router.replace("/onboarding");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogle() {
    setGoogleLoading(true);
    // Probe first — see the note in the login page's handler.
    const { available, reason } = await authApi.isGoogleOAuthAvailable();
    if (!available) {
      setGoogleLoading(false);
      toast.error(reason ?? "Google sign-up isn't available on this server.", {
        description: "Create an account with your email instead.",
      });
      return;
    }
    window.location.href = authApi.googleLoginUrl();
  }

  return (
    <AuthShell
      title="Create your account"
      description="Start finding qualified leads in minutes."
      footer={<AuthFooterLink prompt="Already have an account?" href="/login" label="Sign in" />}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <Label htmlFor="fullName">Full name</Label>
          <Input
            id="fullName"
            type="text"
            placeholder="Jordan Reyes"
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Work email</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@company.com"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="company">Company</Label>
          <Input
            id="company"
            type="text"
            placeholder="Acme Inc."
            autoComplete="organization"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              placeholder="Create a password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              className="pr-9"
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          <p className="text-xs text-muted-foreground">Must be at least 8 characters.</p>
        </div>

        <div className="flex items-start gap-2">
          <Checkbox
            id="terms"
            checked={agreedToTerms}
            onCheckedChange={(c) => setAgreedToTerms(c === true)}
            disabled={loading}
            className="mt-0.5"
          />
          <Label htmlFor="terms" className="font-normal leading-snug text-muted-foreground">
            I agree to the{" "}
            <Link href="#" className="font-medium text-primary hover:underline underline-offset-4">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link href="#" className="font-medium text-primary hover:underline underline-offset-4">
              Privacy Policy
            </Link>
            .
          </Label>
        </div>

        <Button type="submit" variant="gradient" size="lg" disabled={loading} className="mt-1 w-full">
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Creating account...
            </>
          ) : (
            "Create account"
          )}
        </Button>
      </form>

      <div className="my-6 flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="text-xs text-muted-foreground">or continue with</span>
        <Separator className="flex-1" />
      </div>

      <Button
        type="button"
        variant="outline"
        size="lg"
        className="w-full"
        onClick={handleGoogle}
        disabled={googleLoading}
      >
        {googleLoading ? <Loader2 className="size-4 animate-spin" /> : <GoogleIcon />}
        Continue with Google
      </Button>
    </AuthShell>
  );
}
