import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { useRegister } from "@/api/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { getErrorMessage, getFieldErrors } from "@/lib/api";

import { AuthLayout } from "./AuthLayout";

const schema = z
  .object({
    first_name: z.string().trim().min(1, "First name is required").max(150),
    last_name: z.string().trim().min(1, "Last name is required").max(150),
    email: z.string().trim().min(1, "Email is required").email("Enter a valid email address"),
    password: z.string().min(8, "Use at least 8 characters").max(128).regex(/\D/, "Password can't be only numbers"),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "Passwords don't match" });
type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const registerUser = useRegister();
  const navigate = useNavigate();
  const { register, handleSubmit, setError, formState: { errors } } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async ({ confirm: _confirm, ...values }) => {
    try {
      await registerUser.mutateAsync(values);
      toast.success("Welcome! Your account is ready.");
      navigate("/", { replace: true });
    } catch (error) {
      const fields = getFieldErrors(error);
      Object.entries(fields).forEach(([name, message]) => {
        if (name in schema.innerType().shape) setError(name as keyof FormValues, { message });
      });
    }
  });

  const serverFieldErrors = getFieldErrors(registerUser.error);
  const generalError = registerUser.isError && !Object.keys(serverFieldErrors).some((k) => k !== "non_field_errors" && k !== "detail");

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Get help from our support team and track your requests."
      footer={<>Already have an account? <Link to="/login" className="font-medium text-brand-700 hover:underline">Log in</Link></>}
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {generalError && <Alert variant="error">{getErrorMessage(registerUser.error)}</Alert>}
        <div className="grid grid-cols-2 gap-3">
          <Field id="first_name" label="First name" error={errors.first_name?.message}>
            <Input id="first_name" autoComplete="given-name" aria-invalid={!!errors.first_name} {...register("first_name")} />
          </Field>
          <Field id="last_name" label="Last name" error={errors.last_name?.message}>
            <Input id="last_name" autoComplete="family-name" aria-invalid={!!errors.last_name} {...register("last_name")} />
          </Field>
        </div>
        <Field id="email" label="Email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...register("email")} />
        </Field>
        <Field id="password" label="Password" error={errors.password?.message} hint="At least 8 characters; avoid common passwords.">
          <Input id="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} {...register("password")} />
        </Field>
        <Field id="confirm" label="Confirm password" error={errors.confirm?.message}>
          <Input id="confirm" type="password" autoComplete="new-password" aria-invalid={!!errors.confirm} {...register("confirm")} />
        </Field>
        <Button type="submit" className="w-full" loading={registerUser.isPending}>Create account</Button>
      </form>
    </AuthLayout>
  );
}
