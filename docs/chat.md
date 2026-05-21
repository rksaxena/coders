# Tech Spec: Simple In-Memory Chat Application

## 1. Overview

This specification details a lightweight, real-time chat application allowing two users to connect using arbitrary display names. Conversations are mapped to a specific `chat_id`, allowing sessions to be resumed as long as the application remains running.

### Core Features

* **Anonymous Pairing:** Users can join or create a session using any random string as a username.
* **Session Continuity:** Users can resume an active conversation using a unique `chat_id`.
* **In-Memory Storage:** All active user sessions, room states, and message histories are maintained strictly in-memory.

---

## 2. Architecture & Data Flow

The application utilizes a client-server architecture. Real-time message exchange is handled via WebSockets (or long-polling fallback), while session initialization and history retrieval are handled via standard HTTP REST endpoints.

```
[ User 1 (Alice) ] <---> [ Chat Server ] <---> [ User 2 (Bob) ]
                                |
                    [ In-Memory Storage (Data Structures) ]

```

### State Management (In-Memory Database)

Since the application does not use an external database, data will be stored in thread-safe, global in-memory structures (e.g., Python `dicts` with locks, or concurrent maps).

#### Data Structures

**1. Active Chats (`Chats`)**

* Key: `chat_id` (String / UUID)
* Value: Object containing room metadata.

```json
{
  "chat_id": "c18f2b80-b26c-4b68",
  "created_at": 1787053400,
  "users": ["Alice", "Bob"],
  "status": "ACTIVE" 
}

```

**2. Message Ledger (`Messages`)**

* Key: `chat_id` (String / UUID)
* Value: List of message objects ordered chronologically.

```json
[
  {
    "message_id": "m1",
    "sender": "Alice",
    "content": "Hey! Did you get the spec?",
    "timestamp": 1787053420
  },
  {
    "message_id": "m2",
    "sender": "Bob",
    "content": "Yeah, looking through it now.",
    "timestamp": 1787053445
  }
]

```

---

## 3. Functional Requirements

### 3.1 Session Creation & Joining

* **UC-1 (Create Chat):** A user can initiate a new chat by passing a random username. The system must return a unique `chat_id`.
* **UC-2 (Join Chat):** A second user can join an existing conversation by providing the valid `chat_id` and their chosen username.
* **UC-3 (Capacity Cap):** A maximum of 2 distinct users are allowed per `chat_id`. If a third user attempts to join, the system must reject the request.

### 3.2 Chat Resumption

* **UC-4 (Resume Session):** If a user disconnects or refreshes their client, they can re-enter the chat by providing the `chat_id` and their original username.
* **UC-5 (History Retrieval):** Upon successfully resuming, the server must transmit the historical message log associated with that `chat_id`.

### 3.3 Messaging

* **UC-6 (Real-time Delivery):** When user A sends a message, it must be delivered to user B immediately if they are connected.
* **UC-7 (Immutability):** Once a message is committed to the in-memory ledger, it cannot be edited or deleted.

---

## 4. API & Protocol Specification

### 4.1 REST Endpoints (HTTP)

#### Create a New Chat Room

* **Endpoint:** `POST /api/chat/create`
* **Payload:**
```json
{ "username": "Alice" }

```


* **Response (201 Created):**

```json
    {
      "chat_id": "c18f2b80-b26c-4b68",
      "username": "Alice",
      "status": "WAITING_FOR_PEER"
    }
    ```

#### Join / Resume an Existing Chat
*   **Endpoint:** `POST /api/chat/join`
*   **Payload:**
    
```json
    {
      "chat_id": "c18f2b80-b26c-4b68",
      "username": "Bob"
    }
    ```
*   **Response (200 OK):**
    
```json
    {
      "chat_id": "c18f2b80-b26c-4b68",
      "username": "Bob",
      "status": "CONNECTED",
      "history": [
        { "sender": "Alice", "content": "Hey!", "timestamp": 1787053420 }
      ]
    }
    ```
*   **Error Responses:**
    *   `404 Not Found`: If `chat_id` does not exist in memory.
    *   `403 Forbidden`: If 2 users are already active in the room and the username doesn't match an existing participant (Room Full).

### 4.2 WebSocket Events (Real-Time Communication)
Upon successful HTTP authentication/handshake, the client establishes a persistent connection to `/ws/chat/{chat_id}`.

#### Outbound Event (Client -> Server)
*   **Event:** `SEND_MESSAGE`
*   **Payload:**
    
```json
    {
      "sender": "Alice",
      "content": "Hello world!"
    }
    ```

#### Inbound Event (Server -> Client Broadcast)
*   **Event:** `BROADCAST_MESSAGE`
*   **Payload:**
    
```json
    {
      "message_id": "uuid-v4-string",
      "sender": "Alice",
      "content": "Hello world!",
      "timestamp": 1787053500
    }
    ```

---

## 5. Non-Functional Requirements & Constraints

*   **Volatility:** All data lives exclusively in RAM. Restarting the server application will completely wipe all channels and histories.
*   **Concurrency:** The server implementation must handle race conditions safely (e.g., two users trying to join the exact same slot concurrently).
*   **No Authentication Layer:** No passwords or tokens are required. Possession of the `chat_id` string serves as the sole authorization mechanism to request entry to a room.

---

## 6. Verification & Test Criteria

1.  **Happy Path Test:** Verify User 1 creates a room, receives an ID, User 2 joins using that ID, and messages pass back and forth instantly.
2.  **Reconnection Test:** Verify User 1 closes their browser window, re-opens it, inputs the original `chat_id` and username, and successfully views the previous message logs.
3.  **Boundary Test:** Attempt to force a third user with a unique name into the same room ID; ensure the server responds with an explicit resource constraints error.

```