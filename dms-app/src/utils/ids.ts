import { v4 as uuidv4 } from 'uuid'

export function createClientId(): string {
  return uuidv4()
}
