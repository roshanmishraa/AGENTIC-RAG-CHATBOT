import axios from "axios";
import { useAuthStore } from "../store/authStore";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";


export const api = axios.create({
  baseURL: BASE
});


// ── Attach JWT automatically ──────────────────────────────
api.interceptors.request.use((config) => {

  const token = useAuthStore.getState().accessToken;

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;

});


// ── Auto-refresh on 401 ───────────────────────────────────
api.interceptors.response.use(

  (r) => r,

  async (err) => {

    const orig = err.config;


    if (
      err.response?.status === 401 &&
      !orig._retry
    ) {

      orig._retry = true;


      try {

        const rt =
          useAuthStore.getState().refreshToken;


        const { data } =
          await axios.post(
            `${BASE}/auth/refresh`,
            {
              refresh_token: rt,
            }
          );


        useAuthStore
          .getState()
          .setTokens(
            data.access_token,
            data.refresh_token
          );


        orig.headers.Authorization =
          `Bearer ${data.access_token}`;


        return api(orig);


      } catch {

        useAuthStore
          .getState()
          .logout();

      }

    }


    return Promise.reject(err);

  }

);


// ── Typed API helpers ─────────────────────────────────────

export const authAPI = {

  signup: (
    email: string,
    username: string,
    password: string
  ) =>
    api.post(
      "/auth/signup",
      {
        email,
        username,
        password
      }
    ),


  login: (
    email: string,
    password: string
  ) =>
    api.post(
      "/auth/login",
      {
        email,
        password
      }
    ),


  logout: (
    refreshToken: string
  ) =>
    api.post(
      "/auth/logout",
      {
        refresh_token: refreshToken
      }
    ),


  me: () =>
    api.get(
      "/users/me"
    ),

};



export const usersAPI = {

  me: () =>
    api.get(
      "/users/me"
    ),

  updateMe: (
    payload: { full_name?: string; phone_number?: string; username?: string }
  ) =>
    api.patch(
      "/users/me",
      payload
    ),

};



export const chatAPI = {

  sendMessage: (
    chatId: string,
    query: string,
    documentIds?: string[]
  ) =>
    api.post(
      "/chat/message",
      {
        chat_id: chatId,

        query,

        document_ids:
          documentIds?.length
            ? documentIds
            : undefined,
      }
    ),

  sendImageMessage: (
    chatId: string,
    query: string,
    image: File,
    documentIds?: string[]
  ) => {

    const fd = new FormData();
    fd.append("chat_id", chatId);
    fd.append("query", query);
    fd.append("image", image);
    if (documentIds?.length) {
      fd.append("document_ids", documentIds.join(","));
    }

    return api.post(
      "/chat/message/image",
      fd,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );

  },

  sendVoiceMessage: (
    chatId: string,
    audioBlob: Blob,
    documentIds?: string[]
  ) => {

    const fd = new FormData();
    fd.append("chat_id", chatId);
    fd.append("audio", audioBlob, "recording.webm");
    if (documentIds?.length) {
      fd.append("document_ids", documentIds.join(","));
    }

    return api.post(
      "/chat/message/voice",
      fd,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );

  },

};



export const ingestAPI = {

  uploadDocument: (
    file: File
  ) => {

    const fd = new FormData();

    fd.append(
      "file",
      file
    );


    return api.post(
      "/ingest/upload",
      fd,
      {
        headers: {
          "Content-Type":
            "multipart/form-data",
        },
      }
    );

  },


  listDocuments: () =>
    api.get(
      "/ingest/documents"
    ),

  deleteDocument: (
    documentId: string
  ) =>
    api.delete(
      `/ingest/documents/${documentId}`
    ),

};



export const mediaAPI = {


  analyzeImage: (
    imageFile: File,
    question = "Describe this image."
  ) => {

    const fd = new FormData();

    fd.append(
      "image",
      imageFile
    );

    fd.append(
      "question",
      question
    );


    return api.post(
      "/media/vision",
      fd,
      {
        headers: {
          "Content-Type":
            "multipart/form-data",
        },
      }
    );

  },


  transcribeVoice: (
    blob: Blob
  ) => {

    const fd = new FormData();

    fd.append(
      "audio",
      blob,
      "recording.webm"
    );


    return api.post(
      "/media/voice/transcribe",
      fd,
      {
        headers: {
          "Content-Type":
            "multipart/form-data",
        },
      }
    );

  },


  speak: (
    text: string,
    voice = "alloy"
  ) =>
    api.post(
      "/media/voice/speak",
      {
        text,
        voice
      },
      {
        responseType: "blob"
      }
    ),

};



export const feedbackAPI = {

  submit: (
    messageId: string,
    rating: -1 | 0 | 1,
    comment?: string
  ) =>
    api.post(
      "/feedback",
      {
        message_id: messageId,
        rating,
        comment
      }
    ),

};



export const adminAPI = {

  usage: () =>
    api.get(
      "/admin/usage"
    ),


  users: (
    limit = 50,
    offset = 0
  ) =>
    api.get(
      `/admin/users?limit=${limit}&offset=${offset}`
    ),


  deactivateUser: (
    userId: string
  ) =>
    api.patch(
      `/admin/users/${userId}/deactivate`
    ),


  auditLogs: (
    limit = 50,
    offset = 0
  ) =>
    api.get(
      `/admin/audit-logs?limit=${limit}&offset=${offset}`
    ),

};



export const healthAPI = {

  live: () =>
    api.get(
      "/health/live"
    ),


  ready: () =>
    api.get(
      "/health/ready"
    ),

};



export const evalAPI = {

  evaluate: (
    questions: string[],
    answers: string[],
    contexts: string[][],
    groundTruths?: string[]
  ) =>
    api.post(
      "/eval/rag",
      {
        questions,
        answers,
        contexts,
        ground_truths: groundTruths
      }
    ),

};


export { BASE };