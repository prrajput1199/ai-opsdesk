import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { useLogin } from "@/api/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { getErrorMessage } from "@/lib/api";

import { AuthLayout } from "./AuthLayout";

const schema = z.object({
  email: z.string().trim().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from || "/";
  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login.mutateAsync(values);
      navigate(from, { replace: true });
    } catch {
      /* shown below */
    }
  });

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Log in to your support workspace."
      footer={<>New customer? <Link to="/register" className="font-medium text-brand-700 hover:underline">Create an account</Link></>}
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {login.isError && <Alert variant="error">{getErrorMessage(login.error)}</Alert>}
        <Field id="email" label="Email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" autoFocus aria-invalid={!!errors.email} {...register("email")} />
        </Field>
        <Field id="password" label="Password" error={errors.password?.message}>
          <Input id="password" type="password" autoComplete="current-password" aria-invalid={!!errors.password} {...register("password")} />
        </Field>
        <Button type="submit" className="w-full" loading={login.isPending}>Log in</Button>
      </form>
      {import.meta.env.DEV && (
        <div className="mt-6 rounded-lg border border-dashed border-slate-300 p-3 text-xs text-slate-500">
          <p className="font-medium text-slate-700">Local demo accounts (after <code>seed_demo</code>)</p>
          <p className="mt-1">admin@opsdesk.dev · priya.agent@opsdesk.dev · customer@opsdesk.dev</p>
          <p>Password: OpsDesk@2026 (or your DEMO_PASSWORD)</p>
        </div>
      )}
    </AuthLayout>
  );
}
