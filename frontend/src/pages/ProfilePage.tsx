import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { useChangePassword, useUpdateProfile } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/context/AuthContext";
import { getErrorMessage, getFieldErrors } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const profileSchema = z.object({
  first_name: z.string().trim().min(1, "Required").max(150),
  last_name: z.string().trim().min(1, "Required").max(150),
});
const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Required"),
    new_password: z.string().min(8, "Use at least 8 characters").max(128),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "Passwords don't match" });

export default function ProfilePage() {
  const { user } = useAuth();
  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();

  const profile = useForm<z.infer<typeof profileSchema>>({ resolver: zodResolver(profileSchema) });
  const password = useForm<z.infer<typeof passwordSchema>>({ resolver: zodResolver(passwordSchema) });

  useEffect(() => {
    if (user) profile.reset({ first_name: user.first_name, last_name: user.last_name });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  if (!user) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="Profile & settings" description="Manage your personal details and password." />
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>{user.email} · {user.role.charAt(0) + user.role.slice(1).toLowerCase()}{user.team ? ` · ${user.team.name}` : ""} · Member since {formatDate(user.date_joined)}</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            noValidate
            onSubmit={profile.handleSubmit(async (v) => {
              try {
                await updateProfile.mutateAsync(v);
                toast.success("Profile updated.");
              } catch (e) {
                toast.error(getErrorMessage(e));
              }
            })}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="first_name" label="First name" error={profile.formState.errors.first_name?.message}>
                <Input id="first_name" {...profile.register("first_name")} />
              </Field>
              <Field id="last_name" label="Last name" error={profile.formState.errors.last_name?.message}>
                <Input id="last_name" {...profile.register("last_name")} />
              </Field>
            </div>
            <div className="flex justify-end">
              <Button type="submit" loading={updateProfile.isPending} disabled={!profile.formState.isDirty}>Save changes</Button>
            </div>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>Changing your password signs you out on all other devices.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            noValidate
            onSubmit={password.handleSubmit(async ({ current_password, new_password }) => {
              try {
                await changePassword.mutateAsync({ current_password, new_password });
                password.reset({ current_password: "", new_password: "", confirm: "" });
                toast.success("Password changed.");
              } catch (e) {
                const fields = getFieldErrors(e);
                if (fields.current_password) password.setError("current_password", { message: fields.current_password });
                else if (fields.new_password || fields.non_field_errors) password.setError("new_password", { message: fields.new_password || fields.non_field_errors });
                else toast.error(getErrorMessage(e));
              }
            })}
          >
            <Field id="current_password" label="Current password" error={password.formState.errors.current_password?.message}>
              <Input id="current_password" type="password" autoComplete="current-password" {...password.register("current_password")} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field id="new_password" label="New password" error={password.formState.errors.new_password?.message}>
                <Input id="new_password" type="password" autoComplete="new-password" {...password.register("new_password")} />
              </Field>
              <Field id="confirm_password" label="Confirm new password" error={password.formState.errors.confirm?.message}>
                <Input id="confirm_password" type="password" autoComplete="new-password" {...password.register("confirm")} />
              </Field>
            </div>
            <div className="flex justify-end">
              <Button type="submit" loading={changePassword.isPending}>Update password</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
