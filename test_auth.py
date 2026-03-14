"""
测试登录功能的简单脚本
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_login():
    print("测试登录功能...")

    # 测试正确的凭据
    response = requests.post(f"{BASE_URL}/api/login", json={
        "username": "admin",
        "password": "password123"
    })

    if response.status_code == 200:
        print("✓ 登录成功!")
        data = response.json()
        token = data['access_token']
        print(f"获取到的令牌: {token[:20]}...")

        # 测试获取用户信息
        headers = {"Authorization": f"Bearer {token}"}
        user_response = requests.get(f"{BASE_URL}/api/users/me", headers=headers)

        if user_response.status_code == 200:
            print("✓ 获取用户信息成功!")
            user_data = user_response.json()
            print(f"用户信息: {json.dumps(user_data, indent=2)}")
        else:
            print(f"✗ 获取用户信息失败: {user_response.status_code} - {user_response.text}")

        # 测试无效凭据
        invalid_response = requests.post(f"{BASE_URL}/api/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })

        if invalid_response.status_code == 401:
            print("✓ 正确拒绝了无效凭据")
        else:
            print(f"✗ 应该拒绝无效凭据，但收到: {invalid_response.status_code}")
    else:
        print(f"✗ 登录失败: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_login()