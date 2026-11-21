/// <reference types="vite/client" />

declare module '/contracts/config.json' {
  import { ContractConfig } from './types/contracts';
  const value: ContractConfig;
  export default value;
}
