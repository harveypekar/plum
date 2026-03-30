using UnityEngine;

public class Opener : MonoBehaviour
{
	private GameObject _doorPivot;
	// Start is called once before the first execution of Update after the MonoBehaviour is created
	void Start()
    {
        _doorPivot = GameObject.Find("DoorPivot");
	}

    // Update is called once per frame
    void Update()
    {
		float normalizedT = Time.time % 1.0f;
		float doorAngle = Mathf.Lerp(0, 90, normalizedT);
		_doorPivot.transform.localRotation = Quaternion.Euler(0, doorAngle, 0);
	}
}
