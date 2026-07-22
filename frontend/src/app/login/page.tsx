import { LoginPanel } from '../../components/LoginPanel';

export const metadata = {
  title: '登录与注册 | Obsidian Alpha',
  description: '登录个人选股空间，或创建独立普通用户账号。',
};

export default function Page() {
  return <LoginPanel />;
}
