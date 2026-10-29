import { useCallback, useEffect, useState } from "react";

import { ConfirmButton, ErrorBanner, EmptyState, Field, Spinner } from "../components/ui.jsx";
import {
  acceptFriendRequest,
  listFriendRequests,
  listFriends,
  rejectFriendRequest,
  removeFriend,
  sendFriendRequest,
} from "../lib/api.js";

export function FriendsPage() {
  const [friends, setFriends] = useState([]);
  const [requests, setRequests] = useState({ incoming: [], outgoing: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [username, setUsername] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [friendList, requestList] = await Promise.all([listFriends(), listFriendRequests()]);
      setFriends(friendList);
      setRequests(requestList);
    } catch (problem) {
      setError(problem.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function send(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await sendFriendRequest(username.trim().toLowerCase());
      setUsername("");
      setNotice("Request sent.");
      await load();
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  async function respond(id, accept) {
    setError("");
    try {
      if (accept) await acceptFriendRequest(id);
      else await rejectFriendRequest(id);
      await load();
    } catch (problem) {
      setError(problem.message);
    }
  }

  async function unfriend(id) {
    setError("");
    try {
      await removeFriend(id);
      await load();
    } catch (problem) {
      setError(problem.message);
    }
  }

  if (loading) return <Spinner label="Loading friends" />;

  return (
    <section>
      <h1>Friends</h1>
      <p className="lede">Only accepted friends can see photos you share with friends.</p>

      <ErrorBanner message={error} onRetry={load} />
      {notice && <p className="banner banner-notice">{notice}</p>}

      <form className="filters" onSubmit={send}>
        <Field id="friend-username" label="Add a friend by username">
          <input
            id="friend-username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="username"
            required
          />
        </Field>
        <button className="button" type="submit" disabled={busy}>
          {busy ? "Sending" : "Send request"}
        </button>
      </form>

      <h2>Incoming requests ({requests.incoming.length})</h2>
      {requests.incoming.length === 0 ? (
        <EmptyState title="No incoming requests">
          <p>When somebody asks to be your friend, it appears here.</p>
        </EmptyState>
      ) : (
        <ul className="list">
          {requests.incoming.map((request) => (
            <li key={request.id}>
              <span>
                <strong>@{request.requester_username}</strong> wants to connect
              </span>
              <span className="row">
                <button className="button" type="button" onClick={() => respond(request.id, true)}>
                  Accept
                </button>
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => respond(request.id, false)}
                >
                  Reject
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <h2>Sent requests ({requests.outgoing.length})</h2>
      {requests.outgoing.length === 0 ? (
        <p className="lede">Nothing pending.</p>
      ) : (
        <ul className="list">
          {requests.outgoing.map((request) => (
            <li key={request.id}>
              <span>@{request.addressee_username}</span>
              <span className="meta">Waiting for a reply</span>
            </li>
          ))}
        </ul>
      )}

      <h2>Your friends ({friends.length})</h2>
      {friends.length === 0 ? (
        <EmptyState title="No friends yet">
          <p>Send a request using the username of somebody you know.</p>
        </EmptyState>
      ) : (
        <ul className="list">
          {friends.map((friend) => (
            <li key={friend.id}>
              <span>
                <strong>@{friend.username}</strong> · {friend.display_name}
              </span>
              <ConfirmButton
                className="link"
                prompt={`Remove ${friend.username} from your friends?`}
                onConfirm={() => unfriend(friend.id)}
              >
                Remove
              </ConfirmButton>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
